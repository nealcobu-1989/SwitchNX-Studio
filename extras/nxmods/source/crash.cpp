#include "crash.hpp"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <map>

namespace nxm {

static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

// "0000000080a5c1f4 (main + 0x5a1c34)" -> "main + 0x5a1c34"
// "... (main + 0x10) (Func + 0x4)"     -> "main + 0x10"
static std::string module_part(const std::string& v) {
    size_t a = v.find('(');
    if (a == std::string::npos) return "";
    size_t b = v.find(')', a);
    return b == std::string::npos ? "" : v.substr(a + 1, b - a - 1);
}

static unsigned long long hex_head(const std::string& v) {
    return std::strtoull(trim(v).c_str(), nullptr, 16);
}

Crash parse_crash(const std::string& text) {
    Crash c;
    std::string section, pc;
    bool in_crashed = false;
    size_t pos = 0;
    while (pos < text.size()) {
        size_t nl = text.find('\n', pos);
        std::string line = text.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
        pos = nl == std::string::npos ? text.size() : nl + 1;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (line[0] != ' ') {
            section = trim(line);
            if (section.rfind("Result:", 0) == 0) {
                size_t a = section.find('('), b = section.find(')');
                if (a != std::string::npos && b != std::string::npos) c.result = section.substr(a + 1, b - a - 1);
            }
            in_crashed = section == "Crashed Thread Info:";
            if (section == "Module Info:" || section == "Thread Report:") in_crashed = false;
            continue;
        }
        size_t colon = line.find(':');
        if (colon == std::string::npos) continue;
        std::string key = trim(line.substr(0, colon)), val = trim(line.substr(colon + 1));
        if (section == "Exception Info:") {
            if (key == "Type") c.type = val;
            else if (key == "Address") c.where = module_part(val);
            else if (key == "Fault Address") {
                c.fault = module_part(val);
                unsigned long long a = hex_head(val);
                if (c.fault.empty()) {
                    char buf[24];
                    std::snprintf(buf, sizeof buf, "0x%llx", a);
                    c.fault = buf;
                }
                c.near_null = a < 0x10000;
            }
        } else if (in_crashed) {
            if (key == "PC") pc = module_part(val);
            else if (key.rfind("ReturnAddress", 0) == 0 && c.trace.size() < 6) {
                std::string m = module_part(val);
                if (!m.empty()) c.trace.push_back(m);
            }
        }
    }
    if (c.where.empty()) c.where = pc;
    return c;
}

static bool read_all(const std::string& path, std::string& out, size_t limit) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    out.clear();
    char buf[16384];
    size_t n;
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0 && out.size() < limit) out.append(buf, n);
    std::fclose(f);
    return true;
}

static std::string lower(std::string s) {
    for (auto& ch : s) ch = (char)std::tolower((unsigned char)ch);
    return s;
}

std::vector<Crash> read_crashes(const std::string& dir, const std::string& program_id, size_t max) {
    std::vector<std::pair<long long, std::string>> found;
    std::string want = "_" + lower(program_id) + ".log";
    if (DIR* d = opendir(dir.c_str())) {
        while (dirent* e = readdir(d)) {
            std::string n = e->d_name, l = lower(n);
            if (l.size() <= want.size() || l.compare(l.size() - want.size(), want.size(), want) != 0) continue;
            found.push_back({std::atoll(n.c_str()), n});
        }
        closedir(d);
    }
    std::sort(found.begin(), found.end(), [](auto& a, auto& b) { return a.first > b.first; });
    if (found.size() > max) found.resize(max);
    std::vector<Crash> out;
    for (auto& [ts, name] : found) {
        std::string text;
        // the part that matters is at the top; the thread report can be long
        if (!read_all(dir + "/" + name, text, 64 * 1024)) continue;
        Crash c = parse_crash(text);
        c.log = dir + "/" + name;
        c.when = ts;
        std::string jpg = c.log.substr(0, c.log.size() - 4) + ".jpg";
        if (FILE* f = std::fopen(jpg.c_str(), "rb")) { std::fclose(f); c.jpg = jpg; }
        out.push_back(c);
    }
    std::map<std::string, int> spots;
    for (auto& c : out) if (!c.where.empty()) ++spots[c.where];
    for (auto& c : out) if (!c.where.empty()) c.same = spots[c.where];
    return out;
}

}  // namespace nxm
