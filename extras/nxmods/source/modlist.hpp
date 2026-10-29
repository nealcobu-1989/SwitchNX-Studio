// SkyNX Mods: turn the mods of a Skyrim pack on and off on the Switch itself.
//
// The game loads the plugins named in Skyrim_aoc.ccc (in the AOC title's romfs
// on the SD). A plugin that isn't in that list doesn't load. Lines starting with
// '#' are skipped by the game, but they still count toward the list's size
// limit (4096 bytes), so a plugin that's turned off is left out of the file and
// remembered here, in a side file with the full list in order:
//   sdmc:/switch/SkyNXMods/<title>.txt   ('#' in front = off)
// When the .ccc no longer matches that list (the pack was copied again from the
// PC), the side file is rebuilt from the .ccc.
//
// Turning a plugin off when others use it as a master would crash the game at
// start, so the list knows each plugin's masters (from its header, in the
// app title's romfs Data) and says which ones depend on which.
//
// BSAs listed in the inis load whatever the .ccc says. SkyNX Studio writes a
// manifest next to the side file with the full ini lists and which plugins
// each BSA belongs to; saving leaves a BSA out of its ini when all of its
// plugins are off, and puts it back when one comes on.
#pragma once
#include <string>
#include <vector>

namespace nxm {

struct Entry {
    std::string name;
    bool on = true;
    bool game = false;   // Skyrim.esm and the DLC: always on
    bool cc = false;     // Creation Club
    std::vector<std::string> masters;
    bool present = true; // the plugin file is in Data
    // from skyrim-info.txt (SkyNX Studio): what it is
    std::string title, desc_en, desc_es;
    std::vector<std::string> files;   // its BSAs
    unsigned long long size = 0;      // plugin + its BSAs on the SD (0 = unknown)
    // What it weighs, in bytes: its records (the plugin, in memory while it's
    // on) and its BSAs by kind. From SkyNX Studio when it wrote the info file
    // (weighed = true); otherwise a guess from file sizes and BSA names.
    unsigned long long rec = 0, tex = 0, mesh = 0, audio = 0, other = 0;
    bool weighed = false;
};

// Estimated load: 0 light, 1 medium, 2 heavy. Heavy: records of 10 MB or
// more (new lands, big quest mods) or 250 MB or more of textures and meshes.
// Medium: 1.5 MB of records or 40 MB of textures and meshes.
int load_level(const Entry& e);

struct Paths {
    std::string ccc;      // .../01000A10041EB009/romfs/Skyrim_aoc.ccc
    std::string data;     // .../01000A10041EA000/romfs/Data
    std::string romfs;    // .../01000A10041EA000/romfs (the inis)
    std::string side;     // sdmc:/switch/SkyNXMods/skyrim.txt
    std::string manifest; // sdmc:/switch/SkyNXMods/skyrim-ini.txt, written by SkyNX Studio
    std::string info;     // sdmc:/switch/SkyNXMods/skyrim-info.txt: what each plugin is
    std::string pc;       // sdmc:/switch/SkyNXMods/skyrim-pc.txt: the list as the PC copied it
    std::string sd;       // the card's root
    std::vector<std::string> metadata;   // romfs_metadata.bin of both titles
};

// An ini archive list as the PC project has it (from the manifest). A BSA in
// it whose plugins are all off is left out when the list is saved.
struct IniList {
    std::string file, key;
    std::vector<std::string> full;
};

Paths default_paths(const std::string& sd_root);

extern bool spanish;   // messages in Spanish

class ModList {
public:
    bool load(const Paths& p, std::string& error);
    // Changes in memory; save() writes them.
    std::vector<std::string> dependents(size_t i) const;       // on plugins that need entries[i]
    std::vector<std::string> missing_masters(size_t i) const;   // masters of entries[i] that are off
    std::vector<std::string> absent_masters(size_t i) const;    // masters that aren't in the list at all
    void set(size_t i, bool on);
    void set_name(const std::string& name, bool on);
    bool dirty() const { return dirty_; }
    size_t ccc_bytes() const;            // size of the .ccc save() would write
    bool save(std::string& error);
    // BSAs listed in the inis that belong to entries[i] (they go with it)
    std::vector<std::string> ini_bsas(size_t i) const;
    // after save(): inis that were left as they were because they changed
    // since the PC copied them
    std::vector<std::string> skipped_inis;
    // Back to the list as the PC copied it, or as it was before this tool
    // first saved. Returns how many changed; -1 when there's no such list.
    int restore_pc();
    int restore_original();
    // Every mod off but the game, the Creation Club and the unofficial patches:
    // a clean base to switch groups back on when looking for a culprit.
    // Returns how many went off.
    int all_off();
    // Creation Club entries nothing that's on needs as a master go off. With
    // the_patch, the unofficial Creation Club patch (which uses most of them
    // as masters) goes off first. Returns how many went off.
    int cc_off_unneeded(bool the_patch);
    int cc_on_all();             // every Creation Club entry on again
    // BSAs the game opens with the list as it is now: the inis' lists (the
    // language ini's list 2 over Skyrim.ini's), the plugins' own and one per
    // Creation Club entry. Approximate: names in the inis that don't exist count.
    int open_bsas() const;
    // Saved lists (slots 1 to SLOTS) in switch/SkyNXMods/lists: which plugins are
    // on, to switch between mini lists while testing. load_slot returns how many
    // changed (-1: the slot is empty); slot_label is "" for an empty slot.
    static const int SLOTS = 5;
    bool save_slot(int n);
    int load_slot(int n);
    std::string slot_label(int n) const;
    bool has_info() const { return has_info_; }
    // records of the plugins that are on (what stays in memory all the time)
    unsigned long long active_records() const;
    int heavy_on() const;   // heavy mods that are on
    unsigned long long data_bytes = 0;   // everything in the mod Data folder
    unsigned long long sd_free = 0;      // free space on the card
    std::vector<Entry> entries;
    static const size_t LIMIT = 4096;

private:
    Paths paths_;
    std::string newline_ = "\r\n";
    bool dirty_ = false;
    std::vector<IniList> inis_;
    std::vector<std::pair<std::string, std::vector<std::string>>> owners_;   // bsa, plugins
    std::string ccc_text() const;
    const std::vector<std::string>* owners_of(const std::string& bsa) const;
    bool dropped(const std::string& bsa) const;
    void load_manifest();
    void load_info();
    int apply_on(const std::vector<std::string>& on_names, bool only_listed);
    bool has_info_ = false;
    void save_inis();
};

std::vector<std::string> read_masters(const std::string& plugin_path);
std::string lower(std::string s);

}  // namespace nxm
