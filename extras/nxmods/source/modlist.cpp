#include "modlist.hpp"

#include <map>
#include <set>

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/statvfs.h>

namespace nxm {

bool spanish = false;
static std::string T(const char* en, const char* es) { return spanish ? es : en; }

static const char* GAME[] = {"skyrim.esm", "update.esm", "dawnguard.esm", "hearthfires.esm",
                             "dragonborn.esm", "hyrule.esm"};

std::string lower(std::string s) {
    for (auto& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

static bool read_file(const std::string& path, std::string& out) {
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    char buf[8192];
    size_t n;
    out.clear();
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) out.append(buf, n);
    std::fclose(f);
    return true;
}

static bool write_file(const std::string& path, const std::string& data) {
    // write next to it, then replace: a card pulled out halfway keeps the old file
    std::string tmp = path + ".tmp";
    FILE* f = std::fopen(tmp.c_str(), "wb");
    if (!f) return false;
    bool ok = std::fwrite(data.data(), 1, data.size(), f) == data.size();
    ok = (std::fflush(f) == 0) && ok;
    std::fclose(f);
    if (!ok) { std::remove(tmp.c_str()); return false; }
    std::remove(path.c_str());
    return std::rename(tmp.c_str(), path.c_str()) == 0;
}

static bool exists(const std::string& path) {
    struct stat st;
    return stat(path.c_str(), &st) == 0;
}

static void mkdirs(const std::string& path) {
    for (size_t i = 1; i < path.size(); ++i) {
        if (path[i] == '/') {
            std::string part = path.substr(0, i);
            if (!part.empty() && part.back() != ':') mkdir(part.c_str(), 0777);
        }
    }
}

Paths default_paths(const std::string& sd) {
    Paths p;
    p.ccc = sd + "atmosphere/contents/01000A10041EB009/romfs/Skyrim_aoc.ccc";
    p.data = sd + "atmosphere/contents/01000A10041EA000/romfs/Data";
    p.romfs = sd + "atmosphere/contents/01000A10041EA000/romfs";
    p.side = sd + "switch/SkyNXMods/skyrim.txt";
    p.manifest = sd + "switch/SkyNXMods/skyrim-ini.txt";
    p.info = sd + "switch/SkyNXMods/skyrim-info.txt";
    p.pc = sd + "switch/SkyNXMods/skyrim-pc.txt";
    p.sd = sd;
    p.metadata = {sd + "atmosphere/contents/01000A10041EA000/romfs_metadata.bin",
                  sd + "atmosphere/contents/01000A10041EB009/romfs_metadata.bin"};
    return p;
}

// TES4 header: "TES4", u32 size, u32 flags, ... (24 bytes), then subrecords
// (4-char type, u16 size, data). MAST is a zero-terminated master name.
std::vector<std::string> read_masters(const std::string& plugin_path) {
    std::vector<std::string> out;
    FILE* f = std::fopen(plugin_path.c_str(), "rb");
    if (!f) return out;
    unsigned char hdr[24];
    if (std::fread(hdr, 1, 24, f) != 24 || std::memcmp(hdr, "TES4", 4) != 0) { std::fclose(f); return out; }
    uint32_t size = hdr[4] | (hdr[5] << 8) | (hdr[6] << 16) | ((uint32_t)hdr[7] << 24);
    if (size > (1u << 20)) { std::fclose(f); return out; }
    std::string data(size, '\0');
    size_t got = std::fread(&data[0], 1, size, f);
    std::fclose(f);
    data.resize(got);
    size_t o = 0;
    while (o + 6 <= data.size()) {
        std::string type = data.substr(o, 4);
        uint16_t len = (unsigned char)data[o + 4] | ((unsigned char)data[o + 5] << 8);
        if (o + 6 + len > data.size()) break;
        if (type == "MAST") {
            std::string name = data.substr(o + 6, len);
            size_t z = name.find('\0');
            if (z != std::string::npos) name.resize(z);
            out.push_back(name);
        }
        o += 6 + len;
    }
    return out;
}

static std::vector<std::string> split_lines(const std::string& text, std::string& newline) {
    std::vector<std::string> lines;
    newline = text.find("\r\n") != std::string::npos ? "\r\n" : "\n";
    size_t start = 0;
    // a UTF-8 BOM, if any
    if (text.size() >= 3 && (unsigned char)text[0] == 0xEF && (unsigned char)text[1] == 0xBB &&
        (unsigned char)text[2] == 0xBF) start = 3;
    while (start <= text.size()) {
        size_t end = text.find('\n', start);
        std::string line = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t')) line.pop_back();
        size_t b = line.find_first_not_of(" \t");
        line = b == std::string::npos ? "" : line.substr(b);
        if (!line.empty()) lines.push_back(line);
        if (end == std::string::npos) break;
        start = end + 1;
    }
    return lines;
}

static std::vector<std::string> split(const std::string& s, char sep) {
    std::vector<std::string> out;
    size_t a = 0;
    while (a <= s.size()) {
        size_t b = s.find(sep, a);
        out.push_back(s.substr(a, b == std::string::npos ? std::string::npos : b - a));
        if (b == std::string::npos) break;
        a = b + 1;
    }
    return out;
}

static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r"), b = s.find_last_not_of(" \t\r");
    return a == std::string::npos ? "" : s.substr(a, b - a + 1);
}

static std::vector<std::string> items(const std::string& value) {
    std::vector<std::string> out;
    for (auto& x : split(value, ',')) {
        std::string t = trim(x);
        if (!t.empty()) out.push_back(t);
    }
    return out;
}

bool ModList::load(const Paths& p, std::string& error) {
    paths_ = p;
    entries.clear();
    dirty_ = false;
    std::string text;
    if (!read_file(p.ccc, text)) {
        error = T("No load list on the SD (", "No hay lista de carga en la SD (") + p.ccc +
                T("). Copy the pack to the SD first.", "). Copia primero el pack a la SD.");
        return false;
    }
    std::vector<std::string> lines = split_lines(text, newline_);
    std::vector<std::pair<std::string, bool>> list;   // name, on
    for (auto& l : lines) {
        if (l[0] == '#') list.push_back({l.substr(1), false});
        else list.push_back({l, true});
    }
    // the side file wins when its "on" entries are exactly the .ccc's, in order
    std::string side;
    if (read_file(p.side, side)) {
        std::string nl;
        std::vector<std::string> sl = split_lines(side, nl);
        std::vector<std::string> a, b;
        for (auto& e : list) if (e.second) a.push_back(lower(e.first));
        for (auto& l : sl) if (l[0] != '#') b.push_back(lower(l));
        if (a == b) {
            list.clear();
            for (auto& l : sl) {
                if (l[0] == '#') list.push_back({l.substr(1), false});
                else list.push_back({l, true});
            }
        }
    }
    for (auto& e : list) {
        Entry en;
        en.name = e.first;
        en.on = e.second;
        std::string low = lower(en.name);
        for (auto g : GAME) if (low == g) en.game = true;
        en.cc = !en.game && low.rfind("cc", 0) == 0;
        std::string path = p.data + "/" + en.name;
        // Creation Club files are often only in the game's own romfs, out of reach
        en.present = en.game || en.cc || exists(path);
        if (!en.game) en.masters = read_masters(path);
        if (en.game) en.on = true;
        entries.push_back(en);
    }
    load_manifest();
    load_info();
    return true;
}

static unsigned long long file_size(const std::string& path) {
    struct stat st;
    return stat(path.c_str(), &st) == 0 ? (unsigned long long)st.st_size : 0;
}

static unsigned long long tree_size(const std::string& dir, int depth = 0) {
    unsigned long long total = 0;
    DIR* d = opendir(dir.c_str());
    if (!d) return 0;
    while (dirent* e = readdir(d)) {
        std::string n = e->d_name;
        if (n == "." || n == "..") continue;
        std::string p = dir + "/" + n;
        struct stat st;
        if (stat(p.c_str(), &st) != 0) continue;
        if (S_ISDIR(st.st_mode)) { if (depth < 8) total += tree_size(p, depth + 1); }
        else total += (unsigned long long)st.st_size;
    }
    closedir(d);
    return total;
}

static std::string plain_title(const std::string& name) {
    std::string t = name;
    size_t dot = t.rfind('.');
    if (dot != std::string::npos) t.resize(dot);
    return t;
}

void ModList::load_info() {
    has_info_ = false;
    std::map<std::string, size_t> idx;
    for (size_t i = 0; i < entries.size(); ++i) idx[lower(entries[i].name)] = i;
    std::string text;
    if (read_file(paths_.info, text)) {
        for (auto& line : split(text, '\n')) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty() || line[0] == '#') continue;
            auto f = split(line, '\t');
            if (f.size() < 7 || f[0] != "p") continue;
            auto it = idx.find(lower(f[1]));
            if (it == idx.end()) continue;
            Entry& e = entries[it->second];
            e.title = f[2];
            e.desc_en = f[4];
            e.desc_es = f[5];
            e.files.clear();
            for (auto& b : split(f[6], '|')) if (!b.empty()) e.files.push_back(b);
            if (f.size() >= 8) {
                auto w = split(f[7], ':');
                if (w.size() >= 5) {
                    unsigned long long* dst[] = {&e.rec, &e.tex, &e.mesh, &e.audio, &e.other};
                    for (int k = 0; k < 5; ++k) *dst[k] = std::strtoull(w[k].c_str(), nullptr, 10) * 1024ULL;
                    e.weighed = true;
                }
            }
            has_info_ = true;
        }
    }
    for (auto& e : entries) {
        if (e.title.empty()) e.title = e.game ? e.name : plain_title(e.name);
        if (e.game || !e.present) continue;
        unsigned long long own = file_size(paths_.data + "/" + e.name);
        e.size = own;
        std::vector<std::string> bsas = e.files;
        if (bsas.empty()) {
            // without the info file: the BSAs named after the plugin
            std::string stem = plain_title(e.name);
            for (const char* suf : {".bsa", " - Textures.bsa", " - Meshes.bsa", " - Voices.bsa", " - Sounds.bsa"})
                if (file_size(paths_.data + "/" + stem + suf)) bsas.push_back(stem + suf);
        }
        unsigned long long guess_tex = 0, guess_audio = 0;
        for (auto& b : bsas) {
            unsigned long long n = file_size(paths_.data + "/" + b);
            e.size += n;
            std::string l = lower(b);
            if (l.find("voice") != std::string::npos || l.find("sound") != std::string::npos ||
                l.find("music") != std::string::npos) guess_audio += n;
            else guess_tex += n;
        }
        if (!e.weighed) { e.rec = own; e.tex = guess_tex; e.audio = guess_audio; }
    }
    data_bytes = tree_size(paths_.data);
    struct statvfs vs;
    std::string root = paths_.sd.empty() ? "/" : paths_.sd;
    if (statvfs(root.c_str(), &vs) == 0) sd_free = (unsigned long long)vs.f_bavail * vs.f_frsize;
}

int load_level(const Entry& e) {
    const unsigned long long MB = 1ULL << 20;
    unsigned long long gfx = e.tex + e.mesh;
    if (e.rec >= 10 * MB || gfx >= 250 * MB) return 2;
    if (e.rec >= 3 * MB / 2 || gfx >= 40 * MB) return 1;
    return 0;
}

unsigned long long ModList::active_records() const {
    unsigned long long t = 0;
    for (auto& e : entries) if (e.on && !e.game && !e.cc) t += e.rec;
    return t;
}

int ModList::heavy_on() const {
    int n = 0;
    for (auto& e : entries) if (e.on && !e.game && !e.cc && load_level(e) == 2) ++n;
    return n;
}

int ModList::apply_on(const std::vector<std::string>& on_names, bool only_listed) {
    std::set<std::string> on;
    for (auto& n : on_names) on.insert(lower(n));
    int changed = 0;
    for (size_t i = 0; i < entries.size(); ++i) {
        auto& e = entries[i];
        if (e.game) continue;
        bool want = on.count(lower(e.name)) > 0;
        if (only_listed && !want && !e.on) continue;
        if (e.on != want) { set(i, want); ++changed; }
    }
    return changed;
}

int ModList::all_off() {
    int n = 0;
    for (size_t i = 0; i < entries.size(); ++i) {
        const Entry& e = entries[i];
        if (!e.on || e.game || e.cc || lower(e.name).rfind("unofficial skyrim", 0) == 0) continue;
        set(i, false);
        ++n;
    }
    return n;
}

int ModList::cc_off_unneeded(bool the_patch) {
    int n = 0;
    if (the_patch)
        for (size_t i = 0; i < entries.size(); ++i)
            if (entries[i].on && !entries[i].cc && !entries[i].game &&
                lower(entries[i].name).rfind("unofficial skyrim creation club content patch", 0) == 0) {
                set(i, false);
                ++n;
            }
    bool again = true;
    while (again) {       // a Creation Club entry can be a master of another one
        again = false;
        for (size_t i = 0; i < entries.size(); ++i) {
            if (!entries[i].cc || !entries[i].on || !dependents(i).empty()) continue;
            set(i, false);
            ++n;
            again = true;
        }
    }
    return n;
}

int ModList::cc_on_all() {
    int n = 0;
    for (size_t i = 0; i < entries.size(); ++i)
        if (entries[i].cc && !entries[i].on) { set(i, true); ++n; }
    return n;
}

int ModList::open_bsas() const {
    std::set<std::string> s;
    const std::string L1 = "sresourcearchivelist", L2 = "sresourcearchivelist2";
    bool lang2 = false;
    for (auto& l : inis_)
        if (lower(l.key) == L2 && lower(l.file) != "skyrim.ini") lang2 = true;
    for (auto& l : inis_) {
        std::string k = lower(l.key);
        if (k != L1 && k != L2) continue;
        if (k == L2 && lang2 && lower(l.file) == "skyrim.ini") continue;   // the language ini's wins
        for (auto& b : l.full) if (!dropped(b)) s.insert(lower(b));
    }
    for (auto& e : entries) {
        if (!e.on || e.game) continue;
        if (e.cc && e.files.empty()) { s.insert("cc:" + lower(e.name)); continue; }
        for (auto& f : e.files) s.insert(lower(f));
    }
    return (int)s.size();
}

static std::string slot_path(const Paths& p, int n) {
    std::string dir = p.side.substr(0, p.side.rfind('/') + 1);
    return dir + "lists/list" + std::to_string(n) + ".txt";
}

bool ModList::save_slot(int n) {
    std::string path = slot_path(paths_, n);
    mkdirs(path);
    int on = 0;
    std::string body;
    for (auto& e : entries)
        if (e.on && !e.game) { body += e.name + "\n"; if (!e.cc) ++on; }
    std::string head = "# SkyNX Mods: saved list\n# on " + std::to_string(on) + " bsa " +
                       std::to_string(open_bsas()) + "\n";
    return write_file(path, head + body);
}

int ModList::load_slot(int n) {
    std::string text;
    if (!read_file(slot_path(paths_, n), text)) return -1;
    std::vector<std::string> on;
    std::string nl;
    for (auto& l : split_lines(text, nl)) if (!l.empty() && l[0] != '#') on.push_back(l);
    return apply_on(on, false);
}

std::string ModList::slot_label(int n) const {
    std::string text;
    if (!read_file(slot_path(paths_, n), text)) return "";
    std::string nl, out;
    for (auto& l : split_lines(text, nl))
        if (l.rfind("# on ", 0) == 0) {
            auto f = split(l.substr(5), ' ');      // "<n> bsa <m>"
            out = f.empty() ? "" : f[0];
            if (f.size() >= 3) out += "|" + f[2];
            break;
        }
    return out.empty() ? "?" : out;
}

int ModList::restore_pc() {
    std::string text;
    if (!read_file(paths_.pc, text)) return -1;
    std::string nl;
    std::vector<std::string> on;
    for (auto& l : split_lines(text, nl)) if (l[0] != '#') on.push_back(l);
    return apply_on(on, false);
}

int ModList::restore_original() {
    std::string text;
    if (!read_file(paths_.ccc + ".skynx-original", text)) return -1;
    std::string nl;
    std::vector<std::string> on;
    for (auto& l : split_lines(text, nl)) if (l[0] != '#') on.push_back(l);
    return apply_on(on, false);
}

void ModList::load_manifest() {
    inis_.clear();
    owners_.clear();
    std::string text;
    if (!read_file(paths_.manifest, text)) return;
    for (auto& line : split(text, '\n')) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        auto f = split(line, '\t');
        if (f[0] == "ini" && f.size() >= 4) inis_.push_back({f[1], f[2], items(f[3])});
        if (f[0] == "own" && f.size() >= 3)
            owners_.push_back({lower(f[1]), std::vector<std::string>(f.begin() + 2, f.end())});
    }
}

const std::vector<std::string>* ModList::owners_of(const std::string& bsa) const {
    std::string low = lower(bsa);
    for (auto& o : owners_) if (o.first == low) return &o.second;
    return nullptr;
}

// out of its ini when every plugin it belongs to is in the list and off
bool ModList::dropped(const std::string& bsa) const {
    auto own = owners_of(bsa);
    if (!own || own->empty()) return false;
    for (auto& p : *own) {
        bool found = false;
        for (auto& e : entries)
            if (lower(e.name) == lower(p)) { found = true; if (e.on) return false; }
        if (!found) return false;
    }
    return true;
}

std::vector<std::string> ModList::ini_bsas(size_t i) const {
    std::vector<std::string> out;
    std::string me = lower(entries[i].name);
    for (auto& l : inis_)
        for (auto& b : l.full) {
            auto own = owners_of(b);
            if (!own) continue;
            bool mine = false;
            for (auto& p : *own) if (lower(p) == me) mine = true;
            bool seen = false;
            for (auto& x : out) if (lower(x) == lower(b)) seen = true;
            if (mine && !seen) out.push_back(b);
        }
    return out;
}

static std::string join_list(const std::vector<std::string>& v) {
    std::string out;
    for (size_t i = 0; i < v.size(); ++i) out += (i ? ", " : "") + v[i];
    return out;
}

void ModList::save_inis() {
    skipped_inis.clear();
    for (auto& l : inis_) {
        std::string path = paths_.romfs + "/" + l.file, text;
        if (!read_file(path, text)) continue;
        // the last "key=" line of [Archive]
        std::vector<std::string> lines = split(text, '\n');
        std::string section;
        int at = -1;
        for (size_t k = 0; k < lines.size(); ++k) {
            std::string t = trim(lines[k]);
            if (!t.empty() && t[0] == '[' && t.find(']') != std::string::npos) {
                section = lower(trim(t.substr(1, t.find(']') - 1)));
                continue;
            }
            size_t eq = t.find('=');
            if (section == "archive" && eq != std::string::npos && lower(trim(t.substr(0, eq))) == lower(l.key))
                at = (int)k;
        }
        if (at < 0) { skipped_inis.push_back(l.file); continue; }
        std::string& line = lines[at];
        bool cr = !line.empty() && line.back() == '\r';
        std::string body = cr ? line.substr(0, line.size() - 1) : line;
        size_t eq = body.find('=');
        std::vector<std::string> cur = items(body.substr(eq + 1));
        // still the PC's list, maybe with some of its plugins' BSAs out?
        size_t j = 0;
        bool ok = true;
        for (auto& c : cur) {
            while (j < l.full.size() && lower(l.full[j]) != lower(c)) {
                if (!owners_of(l.full[j])) { ok = false; break; }
                ++j;
            }
            if (!ok || j == l.full.size()) { ok = false; break; }
            ++j;
        }
        for (; ok && j < l.full.size(); ++j) if (!owners_of(l.full[j])) ok = false;
        if (!ok) { skipped_inis.push_back(l.file); continue; }
        std::vector<std::string> want;
        for (auto& b : l.full) if (!dropped(b)) want.push_back(b);
        if (want.size() == cur.size()) {
            bool same = true;
            for (size_t k = 0; k < want.size(); ++k) if (lower(want[k]) != lower(cur[k])) same = false;
            if (same) continue;
        }
        line = body.substr(0, eq + 1) + join_list(want) + (cr ? "\r" : "");
        std::string out;
        for (size_t k = 0; k < lines.size(); ++k) out += (k ? "\n" : "") + lines[k];
        std::string orig = path + ".skynx-original";
        if (!exists(orig)) write_file(orig, text);
        if (!write_file(path, out)) skipped_inis.push_back(l.file);
    }
}

std::vector<std::string> ModList::dependents(size_t i) const {
    std::vector<std::string> out;
    std::string me = lower(entries[i].name);
    for (size_t j = 0; j < entries.size(); ++j) {
        if (j == i || !entries[j].on) continue;
        for (auto& m : entries[j].masters)
            if (lower(m) == me) { out.push_back(entries[j].name); break; }
    }
    return out;
}

std::vector<std::string> ModList::missing_masters(size_t i) const {
    std::vector<std::string> out;
    for (auto& m : entries[i].masters) {
        std::string lm = lower(m);
        for (auto& e : entries)
            if (lower(e.name) == lm && !e.on) out.push_back(e.name);
    }
    return out;
}

std::vector<std::string> ModList::absent_masters(size_t i) const {
    std::vector<std::string> out;
    for (auto& m : entries[i].masters) {
        std::string lm = lower(m);
        bool found = false;
        for (auto g : GAME) if (lm == g) found = true;   // the game's own are never in the list
        for (auto& e : entries) if (lower(e.name) == lm) { found = true; break; }
        if (!found) out.push_back(m);
    }
    return out;
}

void ModList::set(size_t i, bool on) {
    if (entries[i].game || entries[i].on == on) return;
    entries[i].on = on;
    dirty_ = true;
}

void ModList::set_name(const std::string& name, bool on) {
    std::string low = lower(name);
    for (size_t i = 0; i < entries.size(); ++i)
        if (lower(entries[i].name) == low) set(i, on);
}

std::string ModList::ccc_text() const {
    std::string out;
    for (auto& e : entries)
        if (e.on) out += e.name + newline_;
    return out;
}

size_t ModList::ccc_bytes() const { return ccc_text().size(); }

bool ModList::save(std::string& error) {
    std::string text = ccc_text();
    if (text.size() > LIMIT) {
        error = T("The list would be ", "La lista quedaría de ") + std::to_string(text.size()) +
                T(" bytes, over the 4096 the game reads.", " bytes, más de los 4096 que lee el juego.");
        return false;
    }
    // the first list this tool ever saw is kept, to go back to it by hand
    std::string orig = paths_.ccc + ".skynx-original";
    if (!exists(orig)) {
        std::string cur;
        if (read_file(paths_.ccc, cur)) write_file(orig, cur);
    }
    if (!write_file(paths_.ccc, text)) {
        error = T("Couldn't write ", "No se pudo escribir ") + paths_.ccc;
        return false;
    }
    std::string side;
    for (auto& e : entries) side += (e.on ? "" : "#") + e.name + "\n";
    mkdirs(paths_.side);
    write_file(paths_.side, side);
    save_inis();
    // Atmosphere's cache of the mods' file list: it makes it again at the next start
    for (auto& m : paths_.metadata) std::remove(m.c_str());
    dirty_ = false;
    return true;
}

}  // namespace nxm
