// SkyNX Mods: the homebrew screen. Same look as the PC app (oak, parchment,
// honey), one list of plugins with a box to turn each on or off.
//
// Built for the Switch with devkitPro (libnx, SDL2, SDL2_ttf, SDL2_image).
// It also builds on a desktop with SDL2 for testing: keys stand in for the
// buttons, and --keys/--shot play a list of presses and save a screenshot.
#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <SDL2/SDL_ttf.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

#include "crash.hpp"
#include "modlist.hpp"

#ifdef __SWITCH__
#include <switch.h>
#define ASSET(p) ("romfs:/" p)
#else
#define ASSET(p) ("romfs/" p)
#endif

namespace {

const int W = 1280, H = 720;
const SDL_Color INK{47, 36, 24, 255}, INK_DIM{107, 90, 67, 255}, INK_FAINT{133, 112, 79, 255},
    HONEY{200, 146, 47, 255}, HONEY_DEEP{168, 118, 31, 255}, ACCENT{224, 169, 59, 255},
    OAK_TEXT{243, 231, 204, 255}, OAK_DIM{205, 183, 145, 255}, OAK_DARK{62, 43, 27, 255},
    HEALTH{168, 53, 45, 255}, STAMINA{94, 139, 59, 255}, AMBER{192, 127, 28, 255};

bool g_es = false;   // Spanish when the console is in Spanish
std::string L(const char* en, const char* es) { return g_es ? es : en; }

enum Btn { B_NONE, B_UP, B_DOWN, B_A, B_B, B_X, B_Y, B_L, B_R, B_ZL, B_ZR, B_PLUS, B_MINUS };

struct Dialog {
    std::string title;
    std::vector<std::string> lines;
    std::string yes, no;               // labels for A and B; empty yes = only B
    std::function<void()> on_yes;
};

struct Ui {
    SDL_Renderer* r = nullptr;
    TTF_Font *body = nullptr, *bold = nullptr, *small = nullptr, *tiny = nullptr, *title = nullptr, *head = nullptr,
             *card = nullptr;
    SDL_Texture *wall = nullptr, *beam = nullptr, *parch = nullptr, *oak = nullptr, *emblem = nullptr;
    std::map<std::string, SDL_Texture*> cache;

    SDL_Texture* text(TTF_Font* f, const std::string& s, SDL_Color c, int* w, int* h) {
        std::string key = std::to_string((size_t)f) + "|" + std::to_string(c.r) + "," + std::to_string(c.g) + "," +
                          std::to_string(c.b) + "," + std::to_string(c.a) + "|" + s;
        auto it = cache.find(key);
        if (it == cache.end()) {
            if (cache.size() > 600) {
                for (auto& kv : cache) SDL_DestroyTexture(kv.second);
                cache.clear();
            }
            SDL_Surface* surf = TTF_RenderUTF8_Blended(f, s.empty() ? " " : s.c_str(), c);
            if (!surf) return nullptr;
            SDL_Texture* t = SDL_CreateTextureFromSurface(r, surf);
            SDL_FreeSurface(surf);
            it = cache.emplace(key, t).first;
        }
        SDL_QueryTexture(it->second, nullptr, nullptr, w, h);
        return it->second;
    }
    int draw(TTF_Font* f, const std::string& s, int x, int y, SDL_Color c, int align = 0) {
        int w = 0, h = 0;
        SDL_Texture* t = text(f, s, c, &w, &h);
        if (!t) return 0;
        SDL_Rect d{align == 1 ? x - w : (align == 2 ? x - w / 2 : x), y, w, h};
        SDL_RenderCopy(r, t, nullptr, &d);
        return w;
    }
    void fill(int x, int y, int w, int h, SDL_Color c) {
        SDL_SetRenderDrawBlendMode(r, SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(r, c.r, c.g, c.b, c.a);
        SDL_Rect rc{x, y, w, h};
        SDL_RenderFillRect(r, &rc);
    }
    void frame(int x, int y, int w, int h, SDL_Color c, int t) {
        fill(x, y, w, t, c); fill(x, y + h - t, w, t, c); fill(x, y, t, h, c); fill(x + w - t, y, t, h, c);
    }
    void tile(SDL_Texture* tex, int x, int y, int w, int h, int size) {
        if (!tex) return;
        SDL_Rect clip{x, y, w, h};
        SDL_RenderSetClipRect(r, &clip);
        for (int yy = y; yy < y + h; yy += size)
            for (int xx = x; xx < x + w; xx += size) {
                SDL_Rect d{xx, yy, size, size};
                SDL_RenderCopy(r, tex, nullptr, &d);
            }
        SDL_RenderSetClipRect(r, nullptr);
    }
    std::vector<std::string> wrap(TTF_Font* f, const std::string& s, int width) {
        std::vector<std::string> out;
        std::string line, word;
        auto fits = [&](const std::string& t) { int w = 0, h = 0; TTF_SizeUTF8(f, t.c_str(), &w, &h); return w <= width; };
        size_t i = 0;
        while (i <= s.size()) {
            size_t sp = s.find(' ', i);
            word = s.substr(i, sp == std::string::npos ? std::string::npos : sp - i);
            std::string cand = line.empty() ? word : line + " " + word;
            if (!line.empty() && !fits(cand)) { out.push_back(line); line = word; }
            else line = cand;
            if (sp == std::string::npos) break;
            i = sp + 1;
        }
        if (!line.empty()) out.push_back(line);
        return out;
    }
    void button(int x, int y, const std::string& b, const std::string& label) {
        // a round button glyph and its action
        fill(x, y + 4, 30, 30, OAK_DARK);
        frame(x, y + 4, 30, 30, ACCENT, 2);
        draw(bold, b, x + 15, y + 5, ACCENT, 2);
        draw(body, label, x + 38, y + 2, OAK_TEXT);
    }
};

std::string with_commas(size_t n) {
    std::string s = std::to_string(n);
    for (int i = (int)s.size() - 3; i > 0; i -= 3) s.insert(i, ",");
    return s;
}

std::string size_text(unsigned long long b) {
    char buf[32];
    if (b >= (1ULL << 30)) std::snprintf(buf, sizeof buf, "%.1f GB", b / 1073741824.0);
    else if (b >= (1ULL << 20)) std::snprintf(buf, sizeof buf, "%.0f MB", b / 1048576.0);
    else if (b >= 1024) std::snprintf(buf, sizeof buf, "%.0f KB", b / 1024.0);
    else std::snprintf(buf, sizeof buf, "%llu B", b);
    std::string out = buf;
    if (g_es) for (auto& c : out) if (c == '.') c = ',';
    return out;
}

const char* MONTHS_EN[] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
const char* MONTHS_ES[] = {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"};

std::string date_text(long long t) {
    int y = 0, mo = 0, d = 0, h = 0, mi = 0;
#ifdef __SWITCH__
    // the console's own time zone
    TimeCalendarTime ct;
    TimeCalendarAdditionalInfo ai;
    if (R_SUCCEEDED(timeToCalendarTimeWithMyRule((u64)t, &ct, &ai))) {
        y = ct.year; mo = ct.month - 1; d = ct.day; h = ct.hour; mi = ct.minute;
    } else
#endif
    {
        time_t tt = (time_t)t;
        struct tm tmv{};
        if (!localtime_r(&tt, &tmv)) return "?";
        y = tmv.tm_year + 1900; mo = tmv.tm_mon; d = tmv.tm_mday; h = tmv.tm_hour; mi = tmv.tm_min;
    }
    char buf[48];
    std::snprintf(buf, sizeof buf, "%d %s %d, %02d:%02d", d, (g_es ? MONTHS_ES : MONTHS_EN)[((mo % 12) + 12) % 12], y, h, mi);
    return buf;
}

std::string load_name(int lv) {
    return lv == 2 ? L("heavy", "pesada") : (lv == 1 ? L("medium", "media") : L("light", "ligera"));
}
SDL_Color load_color(int lv) { return lv == 2 ? HEALTH : (lv == 1 ? AMBER : STAMINA); }

struct Menu {
    std::string title;
    std::vector<std::pair<std::string, std::function<void()>>> items;
    int sel = 0;
};

// How it was opened: from the Album (applet) or over a game (title). Both
// work: it needs little memory. What matters is Skyrim not being suspended in
// the background, since its files change under it.
struct RunMode {
    bool title = true;
    bool skyrim_open = false;
};

std::string join(const std::vector<std::string>& v, const std::string& sep, size_t max = 6) {
    std::string out;
    for (size_t i = 0; i < v.size() && i < max; ++i) out += (i ? sep : "") + v[i];
    if (v.size() > max) out += sep + "+" + std::to_string(v.size() - max);
    return out;
}

class App {
public:
    App(Ui& ui, RunMode mode) : ui_(ui), mode_(mode) {}

    void open(const std::string& sd_root) {
        std::string err;
        if (!list_.load(nxm::default_paths(sd_root), err)) {
            ask(L("Nothing to show", "No hay nada que mostrar"), {err}, "", L("Exit", "Salir"), nullptr);
            fatal_ = true;
        }
        pos_.resize(list_.entries.size());
        for (size_t i = 0; i < pos_.size(); ++i) pos_[i] = (int)i + 1;
        crashes_ = nxm::read_crashes(sd_root + "atmosphere/crash_reports", "01000A10041EA000");
        refilter();
        if (!fatal_ && mode_.skyrim_open)
            ask(L("Skyrim is open", "Skyrim está abierto"),
                {L("It's suspended in the background. Close it (Home, X) before saving: the game reads the list "
                   "when it starts, and changing its files while it's open can close it when it comes back.",
                   "Está suspendido en segundo plano. Ciérralo (Home, X) antes de guardar: el juego lee la lista "
                   "al iniciar, y cambiar sus archivos con el juego abierto puede cerrarlo cuando vuelva.")},
                "", L("Got it", "Entendido"), nullptr);
    }

    // Touch: what was drawn registers where it can be tapped (later = on top).
    // A finger dragged over the list scrolls it; a swipe changes crash.
    void touch_down(int x, int y) {
        t_x0_ = x; t_y0_ = y; t_dragging_ = false; t_sel0_ = sel_;
        t_in_list_ = !menu_ && !dialog_ && !crash_view_ && x < 784 && y > 100 && y < H - 100;
    }
    void touch_move(int x, int y) {
        if (std::abs(y - t_y0_) > 14 || std::abs(x - t_x0_) > 14) t_dragging_ = true;
        if (t_dragging_ && t_in_list_ && !rows_.empty()) {
            sel_ = t_sel0_ + (t_y0_ - y) / (ROW_H / 2);
            clamp();
        }
    }
    bool touch_up(int x, int y) {   // false = quit
        if (!t_dragging_) return tap(x, y);
        if (crash_view_ && !menu_ && !dialog_ && std::abs(x - t_x0_) > 120)
            return handle(x < t_x0_ ? B_R : B_L);   // swipe left: older
        return true;
    }
    bool tap(int x, int y) {
        SDL_Point pt{x, y};
        for (auto it = hits_.rbegin(); it != hits_.rend(); ++it)
            if (SDL_PointInRect(&pt, &it->r)) return it->fn();
        return true;
    }

    bool handle(Btn b) {   // false = quit
        if (crash_view_ && !menu_ && !dialog_) {
            int n = (int)crashes_.size();
            if (b == B_B || b == B_MINUS) crash_view_ = false;
            else if ((b == B_R || b == B_DOWN || b == B_ZR) && crash_i_ + 1 < n) ++crash_i_;
            else if ((b == B_L || b == B_UP || b == B_ZL) && crash_i_ > 0) --crash_i_;
            return true;
        }
        if (menu_ && !dialog_) {
            int n = (int)menu_->items.size();
            if (b == B_UP) menu_->sel = (menu_->sel + n - 1) % n;
            else if (b == B_DOWN) menu_->sel = (menu_->sel + 1) % n;
            else if (b == B_A) {
                auto fn = menu_->items[menu_->sel].second;
                menu_.reset();
                if (fn) fn();
            } else if (b == B_B || b == B_MINUS) menu_.reset();
            return !quit_;
        }
        if (dialog_) {
            if (b == B_A && !dialog_->yes.empty()) {
                auto fn = dialog_->on_yes;
                dialog_.reset();
                if (fn) fn();
            } else if (b == B_B) {
                dialog_.reset();
                if (fatal_) return false;
            }
            return !quit_;
        }
        int n = (int)rows_.size();
        switch (b) {
            case B_UP: if (sel_ > 0) --sel_; break;
            case B_DOWN: if (sel_ + 1 < n) ++sel_; break;
            case B_L: sel_ = std::max(0, sel_ - vis_rows()); break;
            case B_R: sel_ = std::min(n - 1, sel_ + vis_rows()); break;
            case B_ZR: sort_ = (sort_ + 1) % 3; refilter(); say(sort_label()); break;
            case B_ZL: filter_ = (filter_ + 1) % 3; refilter(); say(filter_label()); break;
            case B_A: toggle(); break;
            case B_Y: show_all_ = !show_all_; refilter(); break;
            case B_X: save(); break;
            case B_MINUS: open_menu(); break;
            case B_B: case B_PLUS:
                if (list_.dirty())
                    ask(L("Leave without saving?", "¿Salir sin guardar?"),
                        {L("The changes aren't on the SD yet; the game would load the list as it was.",
                           "Los cambios aún no están en la SD; el juego cargaría la lista como estaba.")},
                        L("Leave", "Salir"), L("Stay", "Quedarme"), [this] { quit_ = true; });
                else return false;
                break;
            default: break;
        }
        clamp();
        return !quit_;
    }

    void draw() {
        Ui& u = ui_;
        hits_.clear();
        u.tile(u.wall, 0, 0, W, H, 512);
        // top beam
        if (u.beam) { SDL_Rect d{0, 0, W, 84}; SDL_RenderCopy(u.r, u.beam, nullptr, &d); }
        u.fill(0, 82, W, 3, OAK_DARK);
        int tx = 38;
        if (u.emblem) { SDL_Rect d{22, 6, 72, 72}; SDL_RenderCopy(u.r, u.emblem, nullptr, &d); tx = 100; }
        int tw = u.draw(u.title, "SKYNX MODS", tx + 2, 14, {0, 0, 0, 120});
        u.draw(u.title, "SKYNX MODS", tx, 12, ACCENT);
        {
            int lx = tx + tw + 40;
            u.draw(u.tiny, L("ESTIMATED LOAD OF WHAT'S ON", "CARGA ESTIMADA DE LO ACTIVO"), lx, 14, OAK_DIM);
            int heavy = list_.heavy_on();
            std::string t = L("Records ~", "Registros ~") + size_text(list_.active_records());
            int w2 = u.draw(u.body, t, lx, 38, OAK_TEXT);
            if (heavy)
                w2 += u.draw(u.body, "  \xC2\xB7  " + std::to_string(heavy) + (heavy == 1 ? L(" heavy", " pesado") : L(" heavy", " pesados")),
                             lx + w2, 38, {232, 140, 120, 255});
            int nb = list_.open_bsas();     // needs the PC's notes on the SD (skyrim-ini.txt)
            if (nb > 0) u.draw(u.body, "  \xC2\xB7  BSA ~" + std::to_string(nb), lx + w2, 38, OAK_TEXT);
        }
        size_t bytes = list_.ccc_bytes();
        SDL_Color bc = bytes > nxm::ModList::LIMIT ? HEALTH : (bytes > 3900 ? AMBER : STAMINA);
        int on = 0, off = 0;
        for (auto& e : list_.entries) if (!e.game && !e.cc) (e.on ? on : off)++;
        u.draw(u.body, (g_es ? "Activos " + std::to_string(on) + "  \xC2\xB7  Apagados " + std::to_string(off)
                     : std::to_string(on) + " on  \xC2\xB7  " + std::to_string(off) + " off"), W - 40, 12, OAK_TEXT, 1);
        u.draw(u.small, ".ccc " + with_commas(bytes) + L(" / 4,096 bytes", " / 4.096 bytes") + (list_.dirty() ? L("  (not saved)", "  (sin guardar)") : ""),
               W - 40, 46, OAK_DIM, 1);
        u.fill(W - 300, 72, 260, 5, OAK_DARK);
        u.fill(W - 300, 72, (int)(260 * std::min<size_t>(bytes, 4096) / 4096), 5, bc);

        // the list
        const int px = 24, py = 100, pw = 760, ph = 520;
        u.tile(u.parch, px, py, pw, ph, 512);
        u.frame(px - 3, py - 3, pw + 6, ph + 6, OAK_DARK, 3);
        const int rows = vis_rows();
        int ry = py + 14;
        if (sort_ != 0) {
            // a view: the order the game loads stays the one LOOT gave
            u.fill(px, py, pw, 40, {62, 43, 27, 225});
            std::string v = sort_ == 1 ? L("Alphabetical view", "Vista alfabética") : L("Heaviest first", "Más pesados primero");
            int w = u.draw(u.bold, v, px + 20, py + 8, ACCENT);
            u.draw(u.tiny, L("  \xC2\xB7  only how it's shown: the load order (LOOT) doesn't change", "  \xC2\xB7  solo la vista: el orden de carga (LOOT) no cambia"),
                   px + 20 + w, py + 10, OAK_TEXT);
            ry = py + 54;
            hit(px, py, pw, 40, [this] { return handle(B_ZR); });
        }
        int top = std::max(0, std::min(sel_ - rows / 2, (int)rows_.size() - rows));
        for (int k = 0; k < rows && top + k < (int)rows_.size(); ++k) {
            int i = rows_[top + k];
            const auto& e = list_.entries[i];
            int y = ry + k * ROW_H;
            // tap a row to pick it, again (or on its box) to turn it on or off
            hit(px + 6, y - 4, pw - 18, ROW_H - 2, [this, r = top + k] {
                if (r == sel_) return handle(B_A);
                sel_ = r;
                return true; });
            hit(px + 6, y - 4, 60, ROW_H - 2, [this, r = top + k] { sel_ = r; return handle(B_A); });
            if (top + k == sel_) {
                u.fill(px + 6, y - 4, pw - 18, ROW_H - 2, {224, 169, 59, 80});
                u.fill(px + 6, y - 4, 5, ROW_H - 2, HONEY);
            }
            int bx = px + 22, by = y + 9;
            if (e.game) {
                u.frame(bx, by, 24, 24, INK_FAINT, 2);
                u.fill(bx + 8, by + 8, 8, 8, INK_FAINT);
            } else {
                u.fill(bx, by, 24, 24, {247, 239, 221, 255});
                u.frame(bx, by, 24, 24, HONEY_DEEP, 2);
                if (e.on) {
                    u.fill(bx + 5, by + 5, 14, 14, HONEY);
                    u.frame(bx + 5, by + 5, 14, 14, HONEY_DEEP, 1);
                }
            }
            SDL_Color nc = e.on ? INK : INK_FAINT;
            int w = u.draw(u.body, e.title, px + 60, y - 1, nc);
            if (!e.on && !e.game) u.fill(px + 60, y + 16, w, 2, INK_FAINT);
            std::string sub = e.name;
            if (e.size) sub += "  \xC2\xB7  " + size_text(e.size);
            u.draw(u.tiny, sub, px + 60, y + 25, INK_FAINT);
            std::string tag = e.game ? L("game", "juego") : (!e.present ? L("file missing", "falta el archivo") : (e.cc ? "Creation Club" : ""));
            if (!tag.empty()) u.draw(u.tiny, tag, px + pw - 34, y + 4, e.present ? INK_FAINT : HEALTH, 1);
            else if (!e.game) {
                int lv = nxm::load_level(e);
                u.draw(u.tiny, g_es ? "carga " + load_name(lv) : load_name(lv) + " load", px + pw - 34, y + 4, load_color(lv), 1);
            }
            // where it is in the load order, so it shows in any view
            u.draw(u.tiny, "#" + std::to_string(pos_[i]), px + pw - 34, y + 25, INK_FAINT, 1);
        }
        if (rows_.empty()) u.draw(u.body, L("Nothing to show with this filter.", "Nada que mostrar con este filtro."), px + 30, py + 20, INK_DIM);
        if ((int)rows_.size() > rows) {
            int track = py + ph - 14 - ry, bar = std::max(30, track * rows / (int)rows_.size());
            int pos = (track - bar) * top / std::max(1, (int)rows_.size() - rows);
            u.fill(px + pw - 14, ry, 4, track, {47, 36, 24, 40});
            u.fill(px + pw - 14, ry + pos, 4, bar, HONEY_DEEP);
        }
        draw_detail();

        // footer
        if (u.beam) { SDL_Rect d{0, H - 72, W, 72}; SDL_RenderCopy(u.r, u.beam, nullptr, &d); }
        u.fill(0, H - 72, W, 3, OAK_DARK);
        int fx = 30, fy = H - 54;
        button(fx, fy, "A", L("On / off", "Activar"), B_A); fx += 165;
        button(fx, fy, "X", L("Save", "Guardar"), B_X); fx += 150;
        button(fx, fy, "Y", show_all_ ? L("Hide CC", "Ocultar CC") : L("Show CC", "Ver CC"), B_Y); fx += 175;
        button(fx, fy, "\xE2\x88\x92", L("More", "Más"), B_MINUS); fx += 120;
        button(fx, fy, "B", L("Exit", "Salir"), B_B);
        std::string st = (mode_.title ? L("Title mode", "Modo título") : L("Applet mode", "Modo applet"));
        if (list_.sd_free) st += L("  \xC2\xB7  SD free ", "  \xC2\xB7  SD libre ") + size_text(list_.sd_free);
        u.draw(u.tiny, st, W - 30, fy - 4, OAK_DIM, 1);
        u.draw(u.tiny, crashes_.empty() ? L("No Skyrim crashes on the SD", "Sin crashes de Skyrim en la SD")
                                        : L("Last crash: ", "Último crash: ") + date_text(crashes_[0].when) + L("  (\xE2\x88\x92 More)", "  (\xE2\x88\x92 Más)"),
               W - 30, fy + 20, crashes_.empty() ? OAK_DIM : ACCENT, 1);
        if (!crashes_.empty()) hit(W - 440, fy + 14, 420, 34, [this] { crash_view_ = true; crash_i_ = 0; return true; });

        if (!toast_.empty() && SDL_GetTicks() < toast_until_) {
            int w = 0, h = 0;
            TTF_SizeUTF8(u.body, toast_.c_str(), &w, &h);
            // over the footer, so the list and its details stay visible
            u.fill(W / 2 - w / 2 - 20, H - 62, w + 40, 48, OAK_DARK);
            u.frame(W / 2 - w / 2 - 20, H - 62, w + 40, 48, ACCENT, 2);
            u.draw(u.body, toast_, W / 2, H - 56, OAK_TEXT, 2);
        }
        if (crash_view_) draw_crash();
        if (menu_) draw_menu();
        if (dialog_) draw_dialog();
    }

private:
    static const int ROWS = 9, ROW_H = 54;
    struct Hit { SDL_Rect r; std::function<bool()> fn; };
    std::vector<Hit> hits_;
    int t_x0_ = 0, t_y0_ = 0, t_sel0_ = 0;
    bool t_dragging_ = false, t_in_list_ = false;
    void hit(int x, int y, int w, int h, std::function<bool()> fn) { hits_.push_back({{x, y, w, h}, std::move(fn)}); }
    // a footer-style button that also answers to a tap
    void button(int x, int y, const std::string& glyph, const std::string& label, Btn b) {
        ui_.button(x, y, glyph, label);
        int w = 0, h = 0;
        TTF_SizeUTF8(ui_.body, label.c_str(), &w, &h);
        hit(x - 8, y - 4, 38 + w + 20, 46, [this, b] { return handle(b); });
    }
    int vis_rows() const { return sort_ != 0 ? ROWS - 1 : ROWS; }
    std::vector<int> pos_;                 // load order position of each entry (1 = first)
    std::vector<nxm::Crash> crashes_;
    bool crash_view_ = false;
    int crash_i_ = 0;
    std::string shot_path_;
    SDL_Texture* shot_ = nullptr;
    Ui& ui_;
    RunMode mode_;
    std::unique_ptr<Menu> menu_;
    int sort_ = 0, filter_ = 0;   // sort: load order, name, load; filter: all, on, off
    nxm::ModList list_;
    std::vector<int> rows_;
    int sel_ = 0;
    bool show_all_ = false, quit_ = false, fatal_ = false, warned_ = false;
    std::unique_ptr<Dialog> dialog_;
    std::string toast_;
    Uint32 toast_until_ = 0;

    void refilter() {
        std::string cur = rows_.empty() ? "" : list_.entries[rows_[sel_]].name;
        rows_.clear();
        for (size_t i = 0; i < list_.entries.size(); ++i) {
            const auto& e = list_.entries[i];
            if (!show_all_ && (e.game || e.cc)) continue;
            if ((filter_ == 1 && !e.on) || (filter_ == 2 && e.on)) continue;
            rows_.push_back((int)i);
        }
        if (sort_ == 1)
            std::stable_sort(rows_.begin(), rows_.end(), [this](int a, int b) {
                return nxm::lower(list_.entries[a].title) < nxm::lower(list_.entries[b].title); });
        if (sort_ == 2)
            std::stable_sort(rows_.begin(), rows_.end(), [this](int a, int b) {
                const auto &x = list_.entries[a], &y = list_.entries[b];
                int la = nxm::load_level(x), lb = nxm::load_level(y);
                if (la != lb) return la > lb;
                return x.rec + (x.tex + x.mesh) / 20 > y.rec + (y.tex + y.mesh) / 20; });
        sel_ = 0;
        for (size_t k = 0; k < rows_.size(); ++k)
            if (list_.entries[rows_[k]].name == cur) sel_ = (int)k;
        clamp();
    }
    void clamp() { sel_ = std::max(0, std::min(sel_, (int)rows_.size() - 1)); }

    void say(const std::string& s) { toast_ = s; toast_until_ = SDL_GetTicks() + 2600; }

    void ask(const std::string& t, std::vector<std::string> lines, const std::string& yes, const std::string& no,
             std::function<void()> fn) {
        dialog_.reset(new Dialog{t, std::move(lines), yes, no, std::move(fn)});
    }

    // everything that would break if `names` went off: who uses them, and who uses those
    std::vector<std::string> all_dependents(const std::string& name) {
        std::vector<std::string> out;
        std::set<std::string> seen{nxm::lower(name)};
        std::vector<std::string> todo{name};
        while (!todo.empty()) {
            std::string n = todo.back();
            todo.pop_back();
            for (size_t i = 0; i < list_.entries.size(); ++i) {
                if (nxm::lower(list_.entries[i].name) != nxm::lower(n)) continue;
                for (auto& d : list_.dependents(i))
                    if (seen.insert(nxm::lower(d)).second) { out.push_back(d); todo.push_back(d); }
            }
        }
        return out;
    }
    std::vector<std::string> all_masters_off(size_t start) {
        std::vector<std::string> out;
        std::set<std::string> seen;
        std::vector<size_t> todo{start};
        while (!todo.empty()) {
            size_t i = todo.back();
            todo.pop_back();
            for (auto& m : list_.missing_masters(i))
                if (seen.insert(nxm::lower(m)).second) {
                    out.push_back(m);
                    for (size_t j = 0; j < list_.entries.size(); ++j)
                        if (nxm::lower(list_.entries[j].name) == nxm::lower(m)) todo.push_back(j);
                }
        }
        return out;
    }

    void toggle() {
        if (rows_.empty()) return;
        size_t i = rows_[sel_];
        auto& e = list_.entries[i];
        if (e.game) { say(L("The game's own files are always on.", "Los archivos del juego siempre están activos.")); return; }
        if (e.on) {
            auto deps = all_dependents(e.name);
            if (deps.empty()) { list_.set(i, false); return; }
            std::string name = e.name;
            ask(L("Others need ", "Otros necesitan ") + name,
                {name + L(" is a master of: ", " es master de: ") + join(deps, ", ", 8) + ".",
                 L("If it goes off and they stay on, the game closes when it starts. Turn them off too?",
                   "Si se apaga y ellos siguen activos, el juego se cierra al iniciar. ¿Los apago también?")},
                L("Turn off all ", "Apagar los ") + std::to_string(deps.size() + 1), L("Cancel", "Cancelar"), [this, deps, name] {
                    list_.set_name(name, false);
                    for (auto& d : deps) list_.set_name(d, false);
                });
            return;
        }
        if (!e.present) { say(L("Its file isn't on the SD. Copy the pack again from the PC.", "Su archivo no está en la SD. Copia el pack otra vez desde el PC.")); return; }
        auto absent = list_.absent_masters(i);
        if (!absent.empty()) {
            ask(L("Missing master", "Falta un master"),
                {e.name + L(" needs ", " necesita ") + join(absent, ", ") + L(", which isn't in the pack.", ", que no está en el pack."),
                 L("Turned on, it would close the game when it starts.", "Activado, cerraría el juego al iniciar.")},
                "", L("Back", "Volver"), nullptr);
            return;
        }
        auto off = all_masters_off(i);
        if (off.empty()) { list_.set(i, true); return; }
        std::string name = e.name;
        ask(L("It needs others", "Necesita otros"),
            {name + L(" needs ", " necesita ") + join(off, ", ", 8) + (off.size() == 1 ? L(", which is off.", ", que está apagado.") : L(", which are off.", ", que están apagados.")),
             (off.size() == 1 ? L("Turn it on too?", "¿Lo activo también?") : L("Turn them on too?", "¿Los activo también?"))},
            L("Turn on all ", "Activar los ") + std::to_string(off.size() + 1), L("Cancel", "Cancelar"), [this, off, name] {
                list_.set_name(name, true);
                for (auto& m : off) list_.set_name(m, true);
            });
    }

    void save() {
        if (!list_.dirty()) { say(L("Nothing changed.", "No hay cambios.")); return; }
        auto doit = [this] {
            std::string err;
            if (!list_.save(err)) { ask(L("Not saved", "No se guardó"), {err}, "", L("Back", "Volver"), nullptr); return; }
            if (list_.skipped_inis.empty())
                say(L("Saved. The game loads the new list next time it starts.", "Guardado. El juego carga la lista nueva la próxima vez que inicie."));
            else
                ask(L("Saved, inis untouched", "Guardado, sin tocar los inis"),
                    {join(list_.skipped_inis, ", ") +
                         L(" changed since the PC copied the pack, so the BSAs listed there stay as they were. "
                           "Copy the pack from the PC again to fix it.",
                           " cambió desde que el PC copió el pack, así que los BSA que lista quedan como estaban. "
                           "Copia el pack otra vez desde el PC para arreglarlo.")},
                    "", L("OK", "Listo"), nullptr);
        };
        if (warned_) { doit(); return; }
        warned_ = true;
        ask(L("Save the list?", "¿Guardar la lista?"),
            {L("Turning mods on or off in the middle of a playthrough can break that save: quests, items and "
               "spells of a mod that's gone stay missing.",
               "Activar o apagar mods a mitad de una partida puede dañar esa partida: las misiones, objetos y "
               "hechizos de un mod que ya no está quedan perdidos."),
             L("The first list is kept next to the original as Skyrim_aoc.ccc.skynx-original.",
               "La primera lista queda guardada al lado como Skyrim_aoc.ccc.skynx-original.")},
            L("Save", "Guardar"), L("Cancel", "Cancelar"), doit);
    }

    void draw_detail() {
        Ui& u = ui_;
        const int dx = 804, dy = 100, dw = 452, dh = 520;
        u.tile(u.parch, dx, dy, dw, dh, 512);
        u.frame(dx - 3, dy - 3, dw + 6, dh + 6, OAK_DARK, 3);
        if (rows_.empty()) return;
        int i = rows_[sel_];
        const auto& e = list_.entries[i];
        int x = dx + 26, y = dy + 18, tw = dw - 52;
        std::string kind = e.game ? L("THE GAME", "EL JUEGO") : (e.cc ? "CREATION CLUB" : "MOD");
        int kw = u.draw(u.bold, kind, x, y, HONEY_DEEP);
        if (!e.game && !e.cc) {
            int lv = nxm::load_level(e);
            std::string chip = g_es ? std::string("CARGA ") + (lv == 2 ? "PESADA" : lv == 1 ? "MEDIA" : "LIGERA")
                                    : std::string(lv == 2 ? "HEAVY" : lv == 1 ? "MEDIUM" : "LIGHT") + " LOAD";
            u.draw(u.bold, "  \xC2\xB7  " + chip, x + kw, y, load_color(lv));
        }
        u.draw(u.bold, e.on ? L("ON", "ACTIVO") : L("OFF", "APAGADO"), dx + dw - 26, y, e.on ? STAMINA : INK_FAINT, 1);
        y += 30;
        auto tl = u.wrap(u.card, e.title, tw);
        for (size_t k = 0; k < tl.size() && k < 3; ++k) { u.draw(u.card, tl[k], x, y, INK); y += 34; }
        u.draw(u.tiny, e.name, x, y + 2, INK_FAINT);
        y += 32;
        u.fill(x, y, tw, 2, HONEY);
        y += 12;
        std::string desc = g_es ? e.desc_es : e.desc_en;
        if (desc.empty())
            desc = list_.has_info()
                ? L("No description yet. Add one in SkyNX Studio, Mods page, and copy the pack again.",
                    "Sin descripción todavía. Agrégala en SkyNX Studio, página Mods, y copia el pack otra vez.")
                : L("Copy the pack with SkyNX Studio 0.9.14 or later to see what each mod is.",
                    "Copia el pack con SkyNX Studio 0.9.14 o posterior para ver qué es cada mod.");
        auto dl = u.wrap(u.small, desc, tw);
        int maxd = 5;
        for (size_t k = 0; k < dl.size() && (int)k < maxd; ++k) {
            std::string line = dl[k];
            if ((int)k == maxd - 1 && dl.size() > (size_t)maxd) line += " …";
            u.draw(u.small, line, x, y, desc == e.desc_en || desc == e.desc_es ? INK : INK_DIM);
            y += 27;
        }
        // the facts, from the bottom up
        std::vector<std::string> facts;
        if (!e.game && !e.cc && e.present) {
            std::string ld = L("Records ~", "Registros ~") + size_text(e.rec) + L(": in memory all the time it's on", ": en memoria todo el tiempo que esté activo");
            if (e.tex + e.mesh) ld += L(". Textures and meshes ", ". Texturas y mallas ") + size_text(e.tex + e.mesh) + L(", only while on screen", ", solo mientras están en pantalla");
            if (e.audio) ld += L(". Audio ", ". Audio ") + size_text(e.audio) + L(", read as it plays", ", se lee al sonar");
            ld += e.weighed ? "." : L(" (rough: from file sizes; copy from SkyNX Studio 0.9.15+ for a closer look).",
                                      " (aprox.: por tamaño de archivos; copia con SkyNX Studio 0.9.15+ para afinarlo).");
            facts.push_back(ld);
        }
        if (e.size) facts.push_back(L("Size on the SD: ", "Tamaño en la SD: ") + size_text(e.size));
        std::vector<std::string> ms;
        for (auto& m : e.masters) {
            std::string l = nxm::lower(m);
            if (l != "skyrim.esm" && l != "update.esm" && l != "dawnguard.esm" && l != "hearthfires.esm" &&
                l != "dragonborn.esm") ms.push_back(m);
        }
        if (!ms.empty()) facts.push_back(L("Needs: ", "Necesita: ") + join(ms, ", ", 4));
        auto deps = list_.dependents(i);
        if (!deps.empty()) facts.push_back(L("Used by: ", "Lo usan: ") + join(deps, ", ", 4));
        auto bs = list_.ini_bsas(i);
        if (!bs.empty()) facts.push_back(L("In the inis, goes with it: ", "En los inis, va con él: ") + join(bs, ", ", 3));
        std::vector<std::string> fl;
        for (size_t fi = 0; fi < facts.size(); ++fi) {
            auto w = u.wrap(u.tiny, facts[fi], tw);
            size_t cap = fi == 0 && !e.game && !e.cc ? 4 : 2;
            for (size_t k = 0; k < w.size() && k < cap; ++k) fl.push_back(w[k]);
        }
        int fy = dy + dh - 18 - (int)fl.size() * 24;
        if (!fl.empty()) u.fill(x, fy - 10, tw, 1, {47, 36, 24, 60});
        for (auto& l : fl) { u.draw(u.tiny, l, x, fy, INK_DIM); fy += 24; }
    }

    std::string sort_label(int k = -1) const {
        const char* en[] = {"Load order (LOOT)", "Alphabetical (view only)", "Heaviest first (view only)"};
        const char* es[] = {"Orden de carga (LOOT)", "Alfabético (solo la vista)", "Más pesados primero (solo la vista)"};
        int i = k < 0 ? sort_ : k;
        return g_es ? es[i] : en[i];
    }
    std::string filter_label(int k = -1) const {
        const char* en[] = {"Showing all", "Showing only the ones on", "Showing only the ones off"};
        const char* es[] = {"Mostrando todos", "Mostrando solo los activos", "Mostrando solo los apagados"};
        int i = k < 0 ? filter_ : k;
        return g_es ? es[i] : en[i];
    }

    void open_menu() {
        menu_.reset(new Menu{L("More", "Más"), {}, 0});
        int ns = (sort_ + 1) % 3, nf = (filter_ + 1) % 3;
        menu_->items.push_back({L("Order: ", "Orden: ") + sort_label(ns) + "   (ZR)",
                                [this, ns] { sort_ = ns; refilter(); }});
        menu_->items.push_back({filter_label(nf) + "   (ZL)",
                                [this, nf] { filter_ = nf; refilter(); }});
        menu_->items.push_back({crashes_.empty() ? L("Skyrim crashes: none on the SD", "Crashes de Skyrim: ninguno en la SD")
                                                 : L("Skyrim crashes (", "Crashes de Skyrim (") + std::to_string(crashes_.size()) + L("), newest first", "), del más reciente"),
                                [this] {
            if (crashes_.empty()) {
                ask(L("No crashes", "Sin crashes"),
                    {L("Atmosphère keeps a report and a screenshot of every game crash in atmosphere/crash_reports. "
                       "There are none of Skyrim there.",
                       "Atmosphère guarda un informe y una captura de cada crash de un juego en atmosphere/crash_reports. "
                       "Ahí no hay ninguno de Skyrim.")}, "", L("Back", "Volver"), nullptr);
                return;
            }
            crash_view_ = true; crash_i_ = 0; }});
        menu_->items.push_back({L("Switch off every mod (to find a culprit)", "Apagar todos los mods (para buscar un culpable)"), [this] {
            ask(L("Switch off every mod?", "¿Apagar todos los mods?"),
                {L("Everything goes off except the game, the Creation Club and the unofficial patches (USSEP and its Creation Club patch).",
                   "Se apaga todo menos el juego, el Creation Club y los parches no oficiales (USSEP y el del Creation Club)."),
                 L("Then switch groups back on and test each time with a new game: the group where it breaks holds the culprit.",
                   "Después enciende por grupos y prueba cada vez con una partida nueva: el grupo donde se daña tiene al culpable."),
                 L("To undo: More » Back to the list the PC copied.",
                   "Para deshacerlo: Más » Volver a la lista que copió el PC.")},
                L("Switch off", "Apagar"), L("Cancel", "Cancelar"), [this] {
                    int n = list_.all_off();
                    say(L("Done: ", "Listo: ") + std::to_string(n) + L(" off. Save to keep it.", " apagados. Guarda para quedarte así."));
                    refilter(); });
        }});
        menu_->items.push_back({L("Creation Club: switch off what nothing needs", "Creation Club: apagar lo que nada necesita"), [this] {
            ask(L("Switch off the Creation Club nothing needs?", "¿Apagar el Creation Club que nada necesita?"),
                {L("Creation Club entries that no plugin that's on uses as a master go off. Each one is a BSA the game keeps open.",
                   "Se apagan los contenidos del Creation Club que ningún plugin encendido usa como master. Cada uno es un BSA que el juego mantiene abierto."),
                 L("With the unofficial Creation Club patch on, most of them stay: it uses them as masters. The next option takes it off too.",
                   "Con el parche no oficial del Creation Club encendido, la mayoría se queda: los usa como masters. La opción siguiente lo apaga también.")},
                L("Switch off", "Apagar"), L("Cancel", "Cancelar"), [this] {
                    int n = list_.cc_off_unneeded(false);
                    say(L("Done: ", "Listo: ") + std::to_string(n) + L(" off. Save to keep it.", " apagados. Guarda para quedarte así."));
                    refilter(); });
        }});
        menu_->items.push_back({L("Creation Club: switch off with its unofficial patch", "Creation Club: apagar junto con su parche no oficial"), [this] {
            ask(L("Switch off the unofficial patch and the Creation Club nothing else needs?", "¿Apagar el parche no oficial y el Creation Club que nada más necesita?"),
                {L("The unofficial Creation Club patch goes off, then every Creation Club entry no other plugin that's on needs.",
                   "Se apaga el parche no oficial del Creation Club y luego todo contenido del Creation Club que ningún otro plugin encendido necesita."),
                 L("What USSEP or other mods use as masters stays on.", "Lo que el USSEP u otros mods usan como master se queda encendido.")},
                L("Switch off", "Apagar"), L("Cancel", "Cancelar"), [this] {
                    int n = list_.cc_off_unneeded(true);
                    say(L("Done: ", "Listo: ") + std::to_string(n) + L(" off. Save to keep it.", " apagados. Guarda para quedarte así."));
                    refilter(); });
        }});
        menu_->items.push_back({L("Creation Club: switch it all on", "Creation Club: encender todo"), [this] {
            int n = list_.cc_on_all();
            say(L("Done: ", "Listo: ") + std::to_string(n) + L(" on. Save to keep it.", " encendidos. Guarda para quedarte así."));
            refilter(); }});
        menu_->items.push_back({L("Saved lists: load one", "Listas guardadas: cargar una"), [this] { open_slots(false); }});
        menu_->items.push_back({L("Saved lists: save this one", "Listas guardadas: guardar esta"), [this] { open_slots(true); }});
        menu_->items.push_back({L("Back to the list the PC copied", "Volver a la lista que copió el PC"), [this] {
            int n = list_.restore_pc();
            say(n < 0 ? L("There's no list from the PC on the SD.", "No hay lista del PC en la SD.")
                      : L("Done: ", "Listo: ") + std::to_string(n) + L(" changed. Save to keep it.", " cambiaron. Guarda para quedarte así."));
            refilter(); }});
        menu_->items.push_back({L("Back to the list before SkyNX Mods", "Volver a la lista de antes de SkyNX Mods"), [this] {
            int n = list_.restore_original();
            say(n < 0 ? L("SkyNX Mods hasn't saved here yet.", "SkyNX Mods todavía no ha guardado aquí.")
                      : L("Done: ", "Listo: ") + std::to_string(n) + L(" changed. Save to keep it.", " cambiaron. Guarda para quedarte así."));
            refilter(); }});
        menu_->items.push_back({L("About the mode and the SD", "Sobre el modo y la SD"), [this] {
            ask(L("Mode and SD", "Modo y SD"),
                {(mode_.title ? L("Opened over a game (title mode).", "Abierto sobre un juego (modo título).")
                              : L("Opened from the Album (applet mode).", "Abierto desde el Álbum (modo applet).")) +
                     L(" Both work: this needs little memory.", " Los dos sirven: esto usa poca memoria."),
                 L("Mods folder: ", "Carpeta de mods: ") + size_text(list_.data_bytes) +
                     (list_.sd_free ? L(". Free on the SD: ", ". Libre en la SD: ") + size_text(list_.sd_free) + "." : "."),
                 L("Changes apply the next time Skyrim starts. Close it first if it's open.",
                   "Los cambios se aplican la próxima vez que abras Skyrim. Ciérralo antes si está abierto.")},
                "", L("Back", "Volver"), nullptr); }});
    }

    std::string slot_text(int n) const {
        std::string lab = list_.slot_label(n);
        std::string head = L("List ", "Lista ") + std::to_string(n) + ": ";
        if (lab.empty()) return head + L("empty", "vacía");
        auto bar = lab.find('|');
        std::string mods = bar == std::string::npos ? lab : lab.substr(0, bar);
        std::string out = head + mods + L(" mods on", " mods activos");
        if (bar != std::string::npos && lab.substr(bar + 1) != "0") out += "  \xC2\xB7  BSA ~" + lab.substr(bar + 1);
        return out;
    }

    // mini lists to switch between while testing: on/off of every plugin
    void open_slots(bool save) {
        menu_.reset(new Menu{save ? L("Save this list in...", "Guardar esta lista en...") : L("Load a saved list", "Cargar una lista guardada"), {}, 0});
        for (int n = 1; n <= nxm::ModList::SLOTS; ++n) {
            menu_->items.push_back({slot_text(n), [this, n, save] {
                if (save) {
                    auto go = [this, n] {
                        say(list_.save_slot(n) ? L("Saved in list ", "Guardada en la lista ") + std::to_string(n) + "."
                                               : L("Couldn't write the list on the SD.", "No pude escribir la lista en la SD."));
                    };
                    if (list_.slot_label(n).empty()) go();
                    else ask(L("Replace list ", "¿Reemplazar la lista ") + std::to_string(n) + L("?", "?"),
                             {slot_text(n)}, L("Replace", "Reemplazar"), L("Cancel", "Cancelar"), go);
                    return;
                }
                int c = list_.load_slot(n);
                say(c < 0 ? L("That list is empty.", "Esa lista está vacía.")
                          : L("List ", "Lista ") + std::to_string(n) + L(" loaded: ", " cargada: ") + std::to_string(c) +
                                L(" changed. Save to keep it.", " cambiaron. Guarda para quedarte así."));
                refilter();
            }});
        }
    }

    // what a fault type means, in plain words
    std::vector<std::string> crash_meaning(const nxm::Crash& c) const {
        std::vector<std::string> out;
        if (c.type == "Data Abort") {
            out.push_back(L("The game used a memory address it couldn't (reading or writing).",
                            "El juego usó una dirección de memoria que no podía (al leer o escribir)."));
            if (c.near_null)
                out.push_back(L("The address is almost zero: something the game expected wasn't there, like an object "
                                "that couldn't be created or loaded. Running out of memory can cause it, and so can a "
                                "broken or missing mod file.",
                                "La dirección es casi cero: algo que el juego esperaba no estaba, como un objeto que no "
                                "se pudo crear o cargar. Puede venir de quedarse sin memoria o de un archivo de mod roto o ausente."));
        } else if (c.type == "User Break") {
            out.push_back(L("The game stopped itself after detecting a serious error. On Switch, running out of memory "
                            "is a frequent reason.",
                            "El juego se detuvo solo al detectar un error grave. En Switch, quedarse sin memoria es una "
                            "razón frecuente."));
        } else if (c.type == "Instruction Abort") {
            out.push_back(L("The game jumped to code that doesn't exist (usually memory already damaged).",
                            "El juego saltó a código que no existe (suele ser memoria ya dañada)."));
        } else if (c.type == "Undefined Instruction") {
            out.push_back(L("An invalid instruction: usually memory already damaged.",
                            "Una instrucción inválida: suele ser memoria ya dañada."));
        } else {
            out.push_back(L("Atmosphère wrote the crash down without a known kind.",
                            "Atmosphère anotó el crash sin un tipo conocido."));
        }
        int spots = 0;
        std::set<std::string> seen;
        for (auto& x : crashes_) if (!x.where.empty() && seen.insert(x.where).second) ++spots;
        if (c.same > 1)
            out.push_back(L("It happened at the same spot in the game's code ", "Pasó en el mismo punto del código del juego ") +
                          std::to_string(c.same) + L(" times: a repeatable crash, likely with one cause.",
                                                     " veces: un crash que se repite, probablemente con una sola causa."));
        else if (crashes_.size() >= 3 && spots * 2 >= (int)crashes_.size())
            out.push_back(L("Recent crashes happen at different spots: that usually points to memory more than to one broken mod.",
                            "Los crashes recientes pasan en puntos distintos: eso suele apuntar más a memoria que a un mod roto concreto."));
        return out;
    }

    void draw_crash() {
        Ui& u = ui_;
        const nxm::Crash& c = crashes_[crash_i_];
        if (shot_path_ != c.jpg) {
            if (shot_) SDL_DestroyTexture(shot_);
            shot_ = nullptr;
            shot_path_ = c.jpg;
            if (!c.jpg.empty())
                if (SDL_Surface* s = IMG_Load(c.jpg.c_str())) { shot_ = SDL_CreateTextureFromSurface(u.r, s); SDL_FreeSurface(s); }
        }
        u.fill(0, 0, W, H, {20, 12, 6, 200});
        hit(0, 0, W, H, [] { return true; });   // nothing under it takes taps
        const int x0 = 30, y0 = 24, w0 = W - 60, h0 = H - 48;
        u.tile(u.parch, x0, y0, w0, h0, 512);
        u.frame(x0 - 4, y0 - 4, w0 + 8, h0 + 8, OAK_DARK, 4);
        u.frame(x0, y0, w0, h0, HONEY, 2);
        u.draw(u.head, L("Skyrim crash ", "Crash de Skyrim ") + std::to_string(crash_i_ + 1) + L(" of ", " de ") +
                           std::to_string(crashes_.size()), x0 + 30, y0 + 16, INK);
        u.draw(u.body, date_text(c.when), x0 + w0 - 30, y0 + 22, INK_DIM, 1);
        u.fill(x0 + 30, y0 + 64, w0 - 60, 2, HONEY);
        // the moment it crashed
        const int sx = x0 + 30, sy = y0 + 84, sw = 640, sh = 360;
        u.fill(sx, sy, sw, sh, OAK_DARK);
        if (shot_) { SDL_Rect d{sx, sy, sw, sh}; SDL_RenderCopy(u.r, shot_, nullptr, &d); }
        else u.draw(u.body, L("No screenshot of this one", "Sin captura de este"), sx + sw / 2, sy + sh / 2 - 16, OAK_DIM, 2);
        u.frame(sx - 2, sy - 2, sw + 4, sh + 4, HONEY_DEEP, 2);
        u.draw(u.tiny, L("What was on screen when it crashed", "Lo que había en pantalla al cerrarse"), sx, sy + sh + 8, INK_FAINT);
        // what it was
        int rx = sx + sw + 30, rw = x0 + w0 - 30 - rx, y = sy;
        u.draw(u.bold, c.type.empty() ? "?" : c.type, rx, y, HEALTH);
        y += 32;
        for (auto& para : crash_meaning(c)) {
            for (auto& l : u.wrap(u.small, para, rw)) { u.draw(u.small, l, rx, y, INK); y += 26; }
            y += 8;
        }
        std::vector<std::string> facts;
        if (!c.where.empty()) facts.push_back(L("Where: ", "Dónde: ") + c.where);
        if (!c.fault.empty()) facts.push_back(L("Address it tried: ", "Dirección que intentó: ") + c.fault);
        if (!c.result.empty()) facts.push_back(L("Code: ", "Código: ") + c.result);
        if (!c.trace.empty()) facts.push_back(L("Came from: ", "Venía de: ") + join(c.trace, ", ", 3));
        int fy = sy + sh + 8 - (int)facts.size() * 24;
        for (auto& f : facts) {
            auto w = u.wrap(u.tiny, f, rw);
            if (!w.empty()) u.draw(u.tiny, w[0], rx, fy, INK_DIM);
            fy += 24;
        }
        std::string file = c.log.substr(c.log.rfind('/') + 1);
        u.draw(u.tiny, L("Full report: atmosphere/crash_reports/", "Informe completo: atmosphere/crash_reports/") + file,
               sx, sy + sh + 36, INK_FAINT);
        int by = y0 + h0 - 56;
        u.fill(x0 + 20, by - 4, w0 - 40, 46, {62, 43, 27, 235});
        int bx = x0 + 40;
        if (crash_i_ > 0) { button(bx, by, "L", L("Newer", "Más reciente"), B_L); }
        bx += 260;
        if (crash_i_ + 1 < (int)crashes_.size()) { button(bx, by, "R", L("Older", "Más antiguo"), B_R); }
        bx += 260;
        button(bx, by, "B", L("Back", "Volver"), B_B);
    }

    void draw_menu() {
        Ui& u = ui_;
        u.fill(0, 0, W, H, {20, 12, 6, 150});
        hit(0, 0, W, H, [this] { return handle(B_B); });   // a tap outside closes it
        const int mw = 640, mx = (W - mw) / 2;
        int mh = 120 + (int)menu_->items.size() * 50, my = (H - mh) / 2;
        hit(mx, my, mw, mh, [] { return true; });
        u.tile(u.parch, mx, my, mw, mh, 512);
        u.frame(mx - 4, my - 4, mw + 8, mh + 8, OAK_DARK, 4);
        u.frame(mx, my, mw, mh, HONEY, 2);
        u.draw(u.head, menu_->title, mx + 36, my + 18, INK);
        int y = my + 76;
        for (size_t k = 0; k < menu_->items.size(); ++k) {
            if ((int)k == menu_->sel) {
                u.fill(mx + 16, y - 4, mw - 32, 44, {224, 169, 59, 90});
                u.fill(mx + 16, y - 4, 5, 44, HONEY);
            }
            u.draw(u.body, menu_->items[k].first, mx + 36, y, INK);
            hit(mx + 16, y - 4, mw - 32, 44, [this, k] { menu_->sel = (int)k; return handle(B_A); });
            y += 50;
        }
    }

    void draw_dialog() {
        Ui& u = ui_;
        u.fill(0, 0, W, H, {20, 12, 6, 170});
        hit(0, 0, W, H, [] { return true; });
        const int dw = 820, dx = (W - dw) / 2;
        std::vector<std::string> lines;
        for (auto& l : dialog_->lines) {
            auto w = u.wrap(u.body, l, dw - 80);
            lines.insert(lines.end(), w.begin(), w.end());
            lines.push_back("");
        }
        int dh = 150 + (int)lines.size() * 30, dy = (H - dh) / 2;
        u.tile(u.parch, dx, dy, dw, dh, 512);
        u.frame(dx - 4, dy - 4, dw + 8, dh + 8, OAK_DARK, 4);
        u.frame(dx, dy, dw, dh, HONEY, 2);
        u.draw(u.head, dialog_->title, dx + 40, dy + 24, INK);
        u.fill(dx + 40, dy + 70, dw - 80, 2, HONEY);
        int y = dy + 86;
        for (auto& l : lines) { u.draw(u.body, l, dx + 40, y, INK); y += 30; }
        int bx = dx + 40, by = dy + dh - 50;
        u.fill(bx - 10, by - 4, dw - 60, 46, {62, 43, 27, 235});
        if (!dialog_->yes.empty()) { button(bx, by, "A", dialog_->yes, B_A); bx += 340; }
        button(bx, by, "B", dialog_->no, B_B);
    }
};

SDL_Texture* load_tex(SDL_Renderer* r, const char* path) {
    SDL_Surface* s = IMG_Load(path);
    if (!s) return nullptr;
    SDL_Texture* t = SDL_CreateTextureFromSurface(r, s);
    SDL_FreeSurface(s);
    return t;
}

}  // namespace

int main(int argc, char** argv) {
    std::string sd = "sdmc:/";
    struct Step { Btn b; int x, y; };   // b == B_NONE: a tap at x, y
    std::vector<Step> script;
    std::string shot;
#ifdef __SWITCH__
    romfsInit();
    if (R_SUCCEEDED(setInitialize())) {
        u64 code = 0;
        SetLanguage lang;
        if (R_SUCCEEDED(setGetSystemLanguage(&code)) && R_SUCCEEDED(setMakeLanguage(code, &lang)))
            g_es = lang == SetLanguage_ES || lang == SetLanguage_ES419;
        setExit();
    }
#else
    // desktop test: <sd root> [--keys up,down,a,x,...] [--shot out.png]
    if (argc > 1) sd = std::string(argv[1]) + "/";
    for (int i = 2; i + 1 < argc; i += 2) {
        std::string k = argv[i], v = argv[i + 1];
        if (k == "--shot") shot = v;
        if (k == "--lang") g_es = v == "es";
        if (k == "--keys") {
            std::map<std::string, Btn> m{{"up", B_UP}, {"down", B_DOWN}, {"a", B_A}, {"b", B_B}, {"x", B_X},
                                         {"y", B_Y}, {"l", B_L}, {"r", B_R}, {"zl", B_ZL}, {"zr", B_ZR}, {"minus", B_MINUS}};
            size_t s = 0;
            while (s <= v.size()) {
                size_t e = v.find(',', s);
                std::string t = v.substr(s, e == std::string::npos ? std::string::npos : e - s);
                if (m.count(t)) script.push_back({m[t], 0, 0});
                else if (t.size() > 1 && t[0] == 't' && t.find('x') != std::string::npos)   // t640x300: a tap
                    script.push_back({B_NONE, std::atoi(t.c_str() + 1), std::atoi(t.c_str() + t.find('x') + 1)});
                if (e == std::string::npos) break;
                s = e + 1;
            }
        }
    }
#endif
    nxm::spanish = g_es;
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_JOYSTICK);
    IMG_Init(IMG_INIT_JPG | IMG_INIT_PNG);
    TTF_Init();
    SDL_Window* win = SDL_CreateWindow("SkyNX Mods", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, W, H, 0);
    Ui ui;
    ui.r = SDL_CreateRenderer(win, -1, shot.empty() ? SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
                                                    : SDL_RENDERER_SOFTWARE);
    ui.body = TTF_OpenFont(ASSET("fonts/Barlow.ttf"), 27);
    ui.small = TTF_OpenFont(ASSET("fonts/Barlow.ttf"), 22);
    ui.bold = TTF_OpenFont(ASSET("fonts/BarlowBold.ttf"), 22);
    ui.tiny = TTF_OpenFont(ASSET("fonts/Barlow.ttf"), 19);
    ui.card = TTF_OpenFont(ASSET("fonts/Cinzel.ttf"), 27);
    ui.title = TTF_OpenFont(ASSET("fonts/Cinzel.ttf"), 44);
    ui.head = TTF_OpenFont(ASSET("fonts/Cinzel.ttf"), 32);
    ui.wall = load_tex(ui.r, ASSET("img/wood-wall.jpg"));
    ui.beam = load_tex(ui.r, ASSET("img/wood-beam.jpg"));
    ui.parch = load_tex(ui.r, ASSET("img/parchment.jpg"));
    ui.emblem = load_tex(ui.r, ASSET("img/emblem.png"));
    if (!ui.body || !ui.title) {
        SDL_Log("fonts missing: %s", TTF_GetError());
        return 1;
    }
    RunMode mode;
#ifdef __SWITCH__
    AppletType at = appletGetAppletType();
    mode.title = at == AppletType_Application || at == AppletType_SystemApplication;
    if (!mode.title && R_SUCCEEDED(pmdmntInitialize())) {
        u64 pid = 0, tid = 0;
        if (R_SUCCEEDED(pmdmntGetApplicationProcessId(&pid)) && R_SUCCEEDED(pminfoInitialize())) {
            if (R_SUCCEEDED(pminfoGetProgramId(&tid, pid))) mode.skyrim_open = tid == 0x01000A10041EA000ULL;
            pminfoExit();
        }
        pmdmntExit();
    }
#else
    mode.title = false;
#endif
    App app(ui, mode);
    app.open(sd);

#ifdef __SWITCH__
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);
    u64 held_since = 0, last_repeat = 0;
    SDL_FingerID finger = -1;
    bool running = true;
    while (running && appletMainLoop()) {
        padUpdate(&pad);
        u64 down = padGetButtonsDown(&pad), held = padGetButtons(&pad);
        Btn b = B_NONE;
        if (down & HidNpadButton_A) b = B_A;
        else if (down & HidNpadButton_B) b = B_B;
        else if (down & HidNpadButton_X) b = B_X;
        else if (down & HidNpadButton_Y) b = B_Y;
        else if (down & HidNpadButton_L) b = B_L;
        else if (down & HidNpadButton_R) b = B_R;
        else if (down & HidNpadButton_ZL) b = B_ZL;
        else if (down & HidNpadButton_ZR) b = B_ZR;
        else if (down & HidNpadButton_Plus) b = B_PLUS;
        else if (down & HidNpadButton_Minus) b = B_MINUS;
        else if (down & (HidNpadButton_Up | HidNpadButton_StickLUp)) b = B_UP;
        else if (down & (HidNpadButton_Down | HidNpadButton_StickLDown)) b = B_DOWN;
        // holding up or down keeps moving
        u64 now = SDL_GetTicks();
        bool ud = held & (HidNpadButton_Up | HidNpadButton_Down | HidNpadButton_StickLUp | HidNpadButton_StickLDown);
        if (!ud) held_since = 0;
        else if (b == B_UP || b == B_DOWN) held_since = now, last_repeat = now;
        else if (held_since && now - held_since > 350 && now - last_repeat > 60) {
            b = (held & (HidNpadButton_Up | HidNpadButton_StickLUp)) ? B_UP : B_DOWN;
            last_repeat = now;
        }
        if (b != B_NONE && !app.handle(b)) running = false;
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) running = false;
            // the touch screen; only the first finger down counts
            if (ev.type != SDL_FINGERDOWN && ev.type != SDL_FINGERMOTION && ev.type != SDL_FINGERUP) continue;
            int tx = (int)(ev.tfinger.x * W), ty = (int)(ev.tfinger.y * H);
            if (ev.type == SDL_FINGERDOWN) {
                if (finger == -1) { finger = ev.tfinger.fingerId; app.touch_down(tx, ty); }
            } else if (ev.tfinger.fingerId == finger) {
                if (ev.type == SDL_FINGERMOTION) app.touch_move(tx, ty);
                else { finger = -1; if (!app.touch_up(tx, ty)) running = false; }
            }
        }
        app.draw();
        SDL_RenderPresent(ui.r);
    }
#else
    if (!shot.empty()) {
        for (auto& st : script) {
            app.draw();   // so taps find what's on screen
            if (st.b == B_NONE) { app.touch_down(st.x, st.y); app.touch_up(st.x, st.y); }
            else app.handle(st.b);
        }
        app.draw();
        SDL_Surface* s = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
        SDL_RenderReadPixels(ui.r, nullptr, SDL_PIXELFORMAT_ARGB8888, s->pixels, s->pitch);
        IMG_SavePNG(s, shot.c_str());
        SDL_FreeSurface(s);
    } else {
        bool running = true;
        while (running) {
            SDL_Event ev;
            while (SDL_PollEvent(&ev)) {
                if (ev.type == SDL_QUIT) running = false;
                // the mouse stands in for a finger
                if (ev.type == SDL_MOUSEBUTTONDOWN) app.touch_down(ev.button.x, ev.button.y);
                if (ev.type == SDL_MOUSEMOTION && (ev.motion.state & SDL_BUTTON_LMASK)) app.touch_move(ev.motion.x, ev.motion.y);
                if (ev.type == SDL_MOUSEBUTTONUP && !app.touch_up(ev.button.x, ev.button.y)) running = false;
                if (ev.type == SDL_KEYDOWN) {
                    Btn b = B_NONE;
                    switch (ev.key.keysym.sym) {
                        case SDLK_UP: b = B_UP; break; case SDLK_DOWN: b = B_DOWN; break;
                        case SDLK_RETURN: b = B_A; break; case SDLK_ESCAPE: b = B_B; break;
                        case SDLK_x: b = B_X; break; case SDLK_y: b = B_Y; break;
                        case SDLK_PAGEUP: b = B_L; break; case SDLK_PAGEDOWN: b = B_R; break;
                        case SDLK_MINUS: b = B_MINUS; break;
                        case SDLK_TAB: b = B_ZR; break; case SDLK_BACKQUOTE: b = B_ZL; break;
                        default: break;
                    }
                    if (b != B_NONE && !app.handle(b)) running = false;
                }
            }
            app.draw();
            SDL_RenderPresent(ui.r);
            SDL_Delay(16);
        }
    }
#endif
    // Fonts keep their files open (stdio on romfs). Close everything before
    // romfs goes away: at exit newlib flushes every open FILE, and one on an
    // unmounted romfs crashed the homebrew menu (2168-0002, _lseek_r).
    for (auto& kv : ui.cache) SDL_DestroyTexture(kv.second);
    ui.cache.clear();
    for (TTF_Font* f : {ui.body, ui.small, ui.bold, ui.tiny, ui.card, ui.title, ui.head})
        if (f) TTF_CloseFont(f);
    for (SDL_Texture* t : {ui.wall, ui.beam, ui.parch, ui.emblem})
        if (t) SDL_DestroyTexture(t);
    SDL_DestroyRenderer(ui.r);
    SDL_DestroyWindow(win);
    TTF_Quit();
    IMG_Quit();
    SDL_Quit();
#ifdef __SWITCH__
    romfsExit();
#endif
    return 0;
}
