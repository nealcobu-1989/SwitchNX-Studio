// The game's crash reports. When a game crashes, Atmosphère writes a report
// and a screenshot of that moment next to each other:
//   sdmc:/atmosphere/crash_reports/<POSIX time>_<program id>.log / .jpg
// This reads Skyrim's, newest first, and keeps what helps to tell one crash
// from another: when, what kind of fault, where in the game's code, and how
// many crashes happened at the same spot.
#pragma once
#include <string>
#include <vector>

namespace nxm {

struct Crash {
    std::string log, jpg;       // paths; jpg empty when there's no screenshot
    long long when = 0;         // POSIX time
    std::string result;         // "2168-0002"
    std::string type;           // "Data Abort", "User Break", ...
    std::string where;          // "main + 0x5a1c34" (empty when unknown)
    std::string fault;          // address it tried to use, when there is one
    bool near_null = false;     // that address is almost zero
    std::vector<std::string> trace;   // the calls that led there ("main + 0x...")
    int same = 1;               // crashes at the same spot among those read
};

// Newest first, at most `max`. `dir` is the crash_reports folder.
std::vector<Crash> read_crashes(const std::string& dir, const std::string& program_id, size_t max = 30);
Crash parse_crash(const std::string& text);

}  // namespace nxm
