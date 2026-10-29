// Logic tests for the load list: make -f Makefile.linux test_modlist && ./test_modlist
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <sys/stat.h>

#include "crash.hpp"
#include "modlist.hpp"

static int fails = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); ++fails; } } while (0)

static std::string root;
static void put(const std::string& rel, const std::string& data) {
    std::string p = root + rel;
    for (size_t i = 1; i < p.size(); ++i) if (p[i] == '/') mkdir(p.substr(0, i).c_str(), 0777);
    std::ofstream(p, std::ios::binary) << data;
}
static std::string get(const std::string& rel) {
    std::ifstream f(root + rel, std::ios::binary);
    std::stringstream ss; ss << f.rdbuf(); return ss.str();
}
static bool has(const std::string& rel) { struct stat st; return stat((root + rel).c_str(), &st) == 0; }
static std::string sub(const std::string& t, const std::string& d) {
    std::string s = t; s += char(d.size() & 255); s += char(d.size() >> 8); return s + d;
}
static std::string plugin(std::initializer_list<const char*> masters) {
    std::string body = sub("HEDR", std::string(12, '\0')) + sub("CNAM", std::string("x\0", 2));
    for (auto m : masters) body += sub("MAST", std::string(m) + '\0') + sub("DATA", std::string(8, '\0'));
    std::string h = "TES4";
    uint32_t n = body.size();
    for (int i = 0; i < 4; ++i) h += char((n >> (8 * i)) & 255);
    return h + std::string(16, '\0') + body;
}
static const std::string CCC = "atmosphere/contents/01000A10041EB009/romfs/Skyrim_aoc.ccc";
static const std::string DATA = "atmosphere/contents/01000A10041EA000/romfs/Data/";
static const std::string META = "atmosphere/contents/01000A10041EA000/romfs_metadata.bin";
static const std::string SIDE = "switch/SkyNXMods/skyrim.txt";

static size_t find(const nxm::ModList& l, const std::string& n) {
    for (size_t i = 0; i < l.entries.size(); ++i) if (l.entries[i].name == n) return i;
    return (size_t)-1;
}

int main() {
    char tmpl[] = "/tmp/nxmods-test-XXXXXX";
    root = std::string(mkdtemp(tmpl)) + "/";
    put(CCC, "\xEF\xBB\xBF" "ccBGSSSE001-Fish.esm\r\nBase.esm\r\nPatch.esp\r\nLone.esp\r\nGone.esp\r\n");
    put(DATA + "ccBGSSSE001-Fish.esm", plugin({"Skyrim.esm"}));
    put(DATA + "Base.esm", plugin({"Skyrim.esm", "Update.esm"}));
    put(DATA + "Patch.esp", plugin({"Skyrim.esm", "Base.esm", "Missing.esm"}));
    put(DATA + "Lone.esp", plugin({"Skyrim.esm"}));
    put(META, "x");
    auto paths = nxm::default_paths(root);

    nxm::ModList l;
    std::string err;
    CHECK(l.load(paths, err));
    CHECK(l.entries.size() == 5);
    CHECK(l.entries[0].name == "ccBGSSSE001-Fish.esm" && l.entries[0].cc);   // BOM gone
    size_t base = find(l, "Base.esm"), patch = find(l, "Patch.esp"), lone = find(l, "Lone.esp"), gone = find(l, "Gone.esp");
    CHECK(!l.entries[gone].present && l.entries[lone].present);
    CHECK(l.dependents(base).size() == 1 && l.dependents(base)[0] == "Patch.esp");
    CHECK(l.absent_masters(patch).size() == 1 && l.absent_masters(patch)[0] == "Missing.esm");
    CHECK(!l.dirty());

    l.set(lone, false);
    l.set(base, false);
    CHECK(l.dirty());
    CHECK(l.missing_masters(patch).size() == 1);
    CHECK(l.dependents(base).size() == 1);          // Patch is still on
    size_t before = l.ccc_bytes();
    CHECK(l.save(err));
    CHECK(!l.dirty());
    std::string ccc = get(CCC);
    CHECK(ccc == "ccBGSSSE001-Fish.esm\r\nPatch.esp\r\nGone.esp\r\n");   // CRLF kept, off ones left out
    CHECK(ccc.size() == before);
    CHECK(get(CCC + ".skynx-original").find("Base.esm") != std::string::npos);
    CHECK(get(SIDE) == "ccBGSSSE001-Fish.esm\nPatch.esp\n#Base.esm\n#Lone.esp\nGone.esp\n" ||
          get(SIDE) == "ccBGSSSE001-Fish.esm\n#Base.esm\nPatch.esp\n#Lone.esp\nGone.esp\n");
    CHECK(!has(META));

    // opened again: the side file brings back the ones that are off, in place
    nxm::ModList l2;
    CHECK(l2.load(paths, err));
    CHECK(l2.entries.size() == 5);
    CHECK(l2.entries[1].name == "Base.esm" && !l2.entries[1].on);
    CHECK(!l2.entries[find(l2, "Lone.esp")].on && l2.entries[find(l2, "Patch.esp")].on);

    // turning one back on and saving keeps the first backup as it was
    l2.set(find(l2, "Base.esm"), true);
    {   // every mod off but the game, CC and the unofficial patches
        nxm::ModList lt;
        CHECK(lt.load(paths, err));
        int n = lt.all_off();
        CHECK(n > 0 && lt.dirty());
        CHECK(lt.entries[0].on);                              // Creation Club stays
        for (auto& e : lt.entries) if (!e.cc && !e.game) CHECK(!e.on);
        CHECK(lt.all_off() == 0);
    }
    {   // Creation Club in bulk: off when nothing on needs it, and back on
        nxm::ModList lc;
        CHECK(lc.load(paths, err));
        int bsas = lc.open_bsas();
        CHECK(lc.cc_off_unneeded(false) == 1 && !lc.entries[0].on);
        CHECK(lc.open_bsas() == bsas - 1 || lc.open_bsas() == bsas);
        CHECK(lc.cc_off_unneeded(true) == 0);
        CHECK(lc.cc_on_all() == 1 && lc.entries[0].on);
    }
    {   // saved mini lists
        nxm::ModList ls;
        CHECK(ls.load(paths, err));
        CHECK(ls.slot_label(2).empty() && ls.load_slot(2) == -1);
        ls.set_name("Lone.esp", false);
        CHECK(ls.save_slot(2) && !ls.slot_label(2).empty());
        ls.set_name("Lone.esp", true);
        ls.set_name("Patch.esp", false);
        CHECK(ls.load_slot(2) == 2);
        bool lone = true, patch = false;
        for (auto& e : ls.entries) { if (e.name == "Lone.esp") lone = e.on; if (e.name == "Patch.esp") patch = e.on; }
        CHECK(!lone && patch);
    }
    CHECK(l2.save(err));
    CHECK(get(CCC) == "ccBGSSSE001-Fish.esm\r\nBase.esm\r\nPatch.esp\r\nGone.esp\r\n");
    CHECK(get(CCC + ".skynx-original").find("Lone.esp") != std::string::npos);

    // the pack copied again from the PC: the .ccc wins, the side file is ignored
    put(CCC, "Lone.esp\nNew.esp\n");
    nxm::ModList l3;
    CHECK(l3.load(paths, err));
    CHECK(l3.entries.size() == 2 && l3.entries[0].on && l3.entries[1].on);

    // over the limit: refused, nothing written
    std::string big;
    for (int i = 0; i < 200; ++i) big += "SomeQuiteLongPluginName" + std::to_string(i) + ".esp\n";
    put(CCC, big);
    nxm::ModList l4;
    CHECK(l4.load(paths, err));
    l4.set(0, false);
    CHECK(!l4.save(err));
    CHECK(err.find("4096") != std::string::npos);
    CHECK(get(CCC) == big);

    // no list at all
    nxm::ModList l5;
    CHECK(!l5.load(nxm::default_paths(root + "nothing/"), err));

    // ini BSAs follow their plugins, through the manifest SkyNX Studio writes
    const std::string INI = "atmosphere/contents/01000A10041EA000/romfs/Skyrim.ini";
    const std::string FULL = "Skyrim - Misc.bsa, BaseB.bsa, Loose.bsa, PatchB.bsa";
    put(CCC, "Base.esm\r\nPatch.esp\r\n");
    put(SIDE, "Base.esm\nPatch.esp\n");
    put(INI, "[General]\r\nsLanguage=ENGLISH\r\n[Archive]\r\nsResourceArchiveList=" + FULL + "\r\n");
    put("switch/SkyNXMods/skyrim-ini.txt", "# comment\nini\tSkyrim.ini\tsResourceArchiveList\t" + FULL +
        "\nown\tBaseB.bsa\tBase.esm\nown\tPatchB.bsa\tPatch.esp\tBase.esm\n");
    nxm::ModList l6;
    CHECK(l6.load(paths, err));
    size_t b6 = find(l6, "Base.esm"), p6 = find(l6, "Patch.esp");
    CHECK(l6.ini_bsas(b6).size() == 2 && l6.ini_bsas(b6)[0] == "BaseB.bsa");
    CHECK(l6.ini_bsas(p6).size() == 1 && l6.ini_bsas(p6)[0] == "PatchB.bsa");
    l6.set(p6, false);                   // PatchB.bsa also belongs to Base, which is on: stays
    CHECK(l6.save(err));
    CHECK(get(INI).find(FULL) != std::string::npos && l6.skipped_inis.empty());
    l6.set(b6, false);
    CHECK(l6.save(err));
    CHECK(get(INI) == "[General]\r\nsLanguage=ENGLISH\r\n[Archive]\r\nsResourceArchiveList=Skyrim - Misc.bsa, Loose.bsa\r\n");
    CHECK(get(INI + ".skynx-original").find(FULL) != std::string::npos);
    nxm::ModList l7;                     // opened again, turned back on: the list comes back
    CHECK(l7.load(paths, err));
    l7.set(find(l7, "Base.esm"), true);
    CHECK(l7.save(err));
    CHECK(get(INI).find("sResourceArchiveList=" + FULL + "\r\n") != std::string::npos);
    // an ini changed by hand since the PC copied it is left alone
    put(INI, "[Archive]\nsResourceArchiveList=Skyrim - Misc.bsa, Mine.bsa, BaseB.bsa, Loose.bsa\n");
    nxm::ModList l8;
    CHECK(l8.load(paths, err));
    l8.set(find(l8, "Base.esm"), false);
    CHECK(l8.save(err));
    CHECK(l8.skipped_inis.size() == 1 && l8.skipped_inis[0] == "Skyrim.ini");
    CHECK(get(INI).find("Mine.bsa, BaseB.bsa") != std::string::npos);

    // what each plugin is, sizes, and going back to the PC's list
    put(DATA + "Base.bsa", std::string(5000, 'b'));
    put("switch/SkyNXMods/skyrim-info.txt",
        "# x\np\tBase.esm\tThe Base Mod\tmod\tA base.\tUna base.\tBase.bsa\n"
        "p\tccBGSSSE001-Fish.esm\tFishing\tcc\tFish.\tPesca.\t\n");
    put("switch/SkyNXMods/skyrim-pc.txt", "ccBGSSSE001-Fish.esm\nBase.esm\nPatch.esp\n");
    put(CCC, "ccBGSSSE001-Fish.esm\r\nBase.esm\r\nPatch.esp\r\n");
    put(SIDE, "ccBGSSSE001-Fish.esm\nBase.esm\nPatch.esp\n");
    nxm::ModList l9;
    CHECK(l9.load(paths, err));
    CHECK(l9.has_info());
    size_t b9 = find(l9, "Base.esm");
    CHECK(l9.entries[b9].title == "The Base Mod" && l9.entries[b9].desc_es == "Una base.");
    CHECK(l9.entries[b9].files.size() == 1 && l9.entries[b9].size == get(DATA + "Base.esm").size() + 5000);
    CHECK(l9.entries[find(l9, "Patch.esp")].title == "Patch");          // no info: the file name
    CHECK(l9.data_bytes > 5000);
    l9.set(find(l9, "Patch.esp"), false);
    l9.set(b9, false);
    CHECK(l9.restore_pc() == 2 && l9.entries[b9].on);
    CHECK(l9.restore_original() >= 0);
    // without weights from the PC: a guess from the files
    CHECK(!l9.entries[b9].weighed && l9.entries[b9].rec == get(DATA + "Base.esm").size() && l9.entries[b9].tex == 5000);

    // weights from the PC: KB of records, textures, meshes, audio, other
    put("switch/SkyNXMods/skyrim-info.txt",
        "p\tBase.esm\tThe Base Mod\tmod\tA base.\tUna base.\tBase.bsa\t20480:300000:1000:5000:10\n"
        "p\tPatch.esp\tPatch\tmod\t\t\t\t2:0:0:0:0\n");
    nxm::ModList l10;
    CHECK(l10.load(paths, err));
    size_t b10 = find(l10, "Base.esm"), p10 = find(l10, "Patch.esp");
    CHECK(l10.entries[b10].weighed && l10.entries[b10].rec == 20480ULL * 1024 && l10.entries[b10].tex == 300000ULL * 1024);
    CHECK(nxm::load_level(l10.entries[b10]) == 2 && nxm::load_level(l10.entries[p10]) == 0);
    l10.set(b10, true); l10.set(p10, true);
    CHECK(l10.active_records() == 20482ULL * 1024 && l10.heavy_on() == 1);
    l10.set(b10, false);
    CHECK(l10.heavy_on() == 0);

    // crash reports: Skyrim's only, newest first, same spot counted
    const std::string CR = "atmosphere/crash_reports/";
    auto report = [](const char* type, const char* addr, const char* fault) {
        std::string t = "Atmosph\xc3\xa8re Crash Report (v1.7):\nResult:                          0x2A8 (2168-0002)\n\n"
                        "Process Info:\n    Process Name:                Skyrim\n"
                        "Exception Info:\n    Type:                        ";
        t += type; t += "\n    Address:                     "; t += addr; t += "\n";
        if (fault) { t += "    Fault Address:               "; t += fault; t += "\n"; }
        t += "Crashed Thread Info:\n    Thread ID:                   0000000000000060\n    Registers:\n"
             "        PC:                      0000000080a5c1f4 (main + 0x5a1c34)\n    Stack Trace:\n"
             "        ReturnAddress[00]:       0000000080b00000 (main + 0x645000)\n"
             "        ReturnAddress[01]:       0000000080b10000 (main + 0x655000) (Foo + 0x10)\n"
             "Module Info:\n    Number of Modules:           05\n";
        return t;
    };
    put(CR + "01761500000_01000a10041ea000.log", report("Data Abort", "0000000080a5c1f4 (main + 0x5a1c34)", "0000000000000010"));
    put(CR + "01761500000_01000a10041ea000.jpg", "jpg");
    put(CR + "01761400000_01000a10041ea000.log", report("Data Abort", "0000000080a5c1f4 (main + 0x5a1c34)", nullptr));
    put(CR + "01761600000_0100000000001000.log", report("User Break", "x", nullptr));   // another program
    put(CR + "01761300000_01000a10041ea000.log", report("User Break", "0000000080000010 (main + 0x10)", nullptr));
    auto cr = nxm::read_crashes(root + CR, "01000A10041EA000");
    CHECK(cr.size() == 3);
    CHECK(cr[0].when == 1761500000LL && !cr[0].jpg.empty() && cr[1].jpg.empty());
    CHECK(cr[0].type == "Data Abort" && cr[0].where == "main + 0x5a1c34" && cr[0].result == "2168-0002");
    CHECK(cr[0].near_null && cr[0].fault == "0x10" && !cr[1].near_null);
    CHECK(cr[0].trace.size() == 2 && cr[0].trace[1] == "main + 0x655000");
    CHECK(cr[0].same == 2 && cr[2].same == 1 && cr[2].type == "User Break");

    std::string cmd = "rm -rf " + root;
    if (std::system(cmd.c_str())) {}
    std::printf(fails ? "%d failed\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
