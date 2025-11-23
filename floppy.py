#!/usr/bin/env python3
import os
import base64
from datetime import datetime

# Optional HTTP client (for Steam API)
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Optional graphics (Pillow)
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

SETTINGS_FILE = "settings.txt"
KNOWN_IDS_FILE = "knownid64.txt"
DATA_FILE = "floppydata.txt"
TOPFLOP_FILE = "topflop.txt"
CURRENT_COUNTS_FILE = "last_current_counts.txt"
TOTAL_COUNTS_FILE = "last_total_counts.txt"
API_KEY_FILE = "floppy.txt"  # optional legacy storage

GRAPHICS_DIR = "graphics"
FLOPPY_ICON = os.path.join(GRAPHICS_DIR, "floppy.png")
JIMY_ICON = os.path.join(GRAPHICS_DIR, "jimy.webp")
OUTPUT_DIR = "image_output"


# ---------- Helpers for settings / ids ----------

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            # example:
            # default_id64=76561198289153961
            # total_calc_order=after
            # apikey=YOUR_STEAM_WEB_API_KEY
            pass

    settings = {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip()
    return settings


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        for k, v in settings.items():
            f.write(f"{k}={v}\n")


def load_known_ids():
    if not os.path.exists(KNOWN_IDS_FILE):
        with open(KNOWN_IDS_FILE, "w", encoding="utf-8") as f:
            pass

    ids = set()
    with open(KNOWN_IDS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.add(line.split()[0])
    return ids


def save_known_ids(ids):
    with open(KNOWN_IDS_FILE, "w", encoding="utf-8") as f:
        for steamid in sorted(ids):
            f.write(steamid + "\n")


# ---------- Last-used counts (for defaults) ----------

def _zero_counts():
    return {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}


def load_last_current_counts():
    if not os.path.exists(CURRENT_COUNTS_FILE):
        with open(CURRENT_COUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("# steamid64 5x 4x 3x 2x 1x (last CURRENT counts)\n")
        return {}

    mapping = {}
    with open(CURRENT_COUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 6:
                continue
            steamid = parts[0]
            try:
                c5, c4, c3, c2, c1 = map(int, parts[1:])
            except ValueError:
                continue
            mapping[steamid] = {
                "5": c5,
                "4": c4,
                "3": c3,
                "2": c2,
                "1": c1,
            }
    return mapping


def save_last_current_counts(mapping):
    with open(CURRENT_COUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("# steamid64 5x 4x 3x 2x 1x (last CURRENT counts)\n")
        for steamid in sorted(mapping.keys()):
            c = mapping[steamid]
            f.write(
                f"{steamid} {c['5']} {c['4']} {c['3']} {c['2']} {c['1']}\n"
            )


def load_last_total_counts():
    if not os.path.exists(TOTAL_COUNTS_FILE):
        with open(TOTAL_COUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("# 5x 4x 3x 2x 1x (last TOTAL counts across all ids)\n")
        return _zero_counts()

    with open(TOTAL_COUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 5:
                return _zero_counts()
            try:
                c5, c4, c3, c2, c1 = map(int, parts)
            except ValueError:
                return _zero_counts()
            return {"5": c5, "4": c4, "3": c3, "2": c2, "1": c1}
    return _zero_counts()


def save_last_total_counts(counts):
    with open(TOTAL_COUNTS_FILE, "w", encoding="utf-8") as f:
        f.write("# 5x 4x 3x 2x 1x (last TOTAL counts across all ids)\n")
        f.write(
            f"{counts['5']} {counts['4']} {counts['3']} {counts['2']} {counts['1']}\n"
        )


# ---------- Steam API key + usernames ----------

def load_api_key(settings=None):
    """
    Priority:
      1) settings['apikey'] from settings.txt
      2) KEY:<base64-encoded> line in floppy.txt (optional legacy)
    """
    if settings is not None:
        key = settings.get("apikey", "").strip()
        if key:
            return key

    if not os.path.exists(API_KEY_FILE):
        return None

    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("KEY:"):
                encoded = line[4:].strip()
                try:
                    return base64.b64decode(encoded).decode("utf-8")
                except Exception:
                    return encoded or None
    return None


def fetch_steam_name(steamid, settings=None):
    """
    Use Steam Web API to get persona name for a steamid.
    """
    if not HAS_REQUESTS:
        return None

    api_key = load_api_key(settings)
    if not api_key:
        return None

    url = (
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        f"?key={api_key}&steamids={steamid}"
    )
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        players = data.get("response", {}).get("players", [])
        if not players:
            return None
        name = players[0].get("personaname")
        if name:
            return name.strip()
    except Exception:
        return None
    return None


# ---------- Top flop leaderboard helpers ----------

def load_topflop():
    """
    Dict: {steamid: {"amt": int, "name": str|None}}
    Lines: steamid flopAmt |username
    """
    if not os.path.exists(TOPFLOP_FILE):
        with open(TOPFLOP_FILE, "w", encoding="utf-8") as f:
            f.write("# steamid64 flopAmt |username (sorted high -> low)\n")
        return {}

    top = {}
    with open(TOPFLOP_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            main, sep, name = line.partition("|")
            main = main.strip()
            name = name.strip() if sep else None
            parts = main.split()
            if len(parts) < 2:
                continue
            steamid = parts[0]
            try:
                amt = int(parts[1])
            except ValueError:
                continue
            top[steamid] = {"amt": amt, "name": name or None}
    return top


def save_topflop(top_dict):
    items = sorted(top_dict.items(), key=lambda kv: kv[1]["amt"], reverse=True)
    with open(TOPFLOP_FILE, "w", encoding="utf-8") as f:
        f.write("# steamid64 flopAmt |username (sorted high -> low)\n")
        for steamid, entry in items:
            amt = entry["amt"]
            name = entry.get("name")
            if name:
                f.write(f"{steamid} {amt} |{name}\n")
            else:
                f.write(f"{steamid} {amt}\n")


def update_topflop_and_get_rank(steamid, flopAmt, settings=None):
    """
    Update leaderboard; attach username if possible.
    Return (rank, top_dict).
    """
    top = load_topflop()
    entry = top.get(steamid, {"amt": 0, "name": None})

    # Always set a name (real or {unknown})
    if entry.get("name") is None:
        name = fetch_steam_name(steamid, settings=settings)
        if name:
            entry["name"] = name
        else:
            entry["name"] = "{unknown}"

    if flopAmt > entry["amt"]:
        entry["amt"] = flopAmt

    top[steamid] = entry

    items = sorted(top.items(), key=lambda kv: kv[1]["amt"], reverse=True)

    rank = None
    for i, (sid, ent) in enumerate(items, start=1):
        if sid == steamid:
            rank = i
            break

    save_topflop(top)

    if rank is None:
        rank = len(items) + 1

    return rank, top


def _get_top10_rows():
    """
    Return list of (rank, steamid, amt, name) sorted by amt desc, top 10.
    """
    top = load_topflop()
    items = sorted(top.items(), key=lambda kv: kv[1]["amt"], reverse=True)
    rows = []
    for i, (sid, entry) in enumerate(items[:10], start=1):
        rows.append((i, sid, entry["amt"], entry.get("name")))
    return rows


# ---------- Input helpers ----------

def _extract_steamid_from_input(raw: str) -> str:
    """
    Accepts either:
      - plain SteamID64: '76561198061128112'
      - URL like 'https://steamcommunity.com/profiles/76561198061128112/...'
    Returns the bare SteamID64 string.
    """
    raw = raw.strip()
    if "steamcommunity.com/profiles/" in raw:
        try:
            part = raw.split("steamcommunity.com/profiles/", 1)[1]
            steamid = part.split("/", 1)[0].strip()
            return steamid
        except Exception:
            # fall back to raw, in case something weird happens
            return raw
    return raw


def prompt_steam_id(settings):
    default_id = settings.get("default_id64", "").strip()
    if default_id:
        inp = input(f"Steam ID64 or profile URL [{default_id}]: ").strip()
        if inp:
            steamid = _extract_steamid_from_input(inp)
        else:
            steamid = default_id
    else:
        while True:
            inp = input("Steam ID64 or profile URL: ").strip()
            if not inp:
                print("Please enter a Steam ID64 or profile link.")
                continue
            steamid = _extract_steamid_from_input(inp)
            if steamid:
                break
            print("Could not parse a Steam ID64, try again.")

    if steamid != default_id:
        use_as_default = input("Set this as default in settings.txt? [y/N]: ").strip().lower()
        if use_as_default == "y":
            settings["default_id64"] = steamid
            save_settings(settings)
    return steamid


def prompt_int(label, default=None):
    while True:
        if default is not None:
            s = input(f"{label} [{default}] (blank for {default}): ").strip()
            if s == "":
                return default
        else:
            s = input(f"{label} (blank for 0): ").strip()
            if s == "":
                return 0
        try:
            return int(s)
        except ValueError:
            print("Please enter an integer or leave blank for the default.")


def prompt_counts(prefix="", defaults=None):
    if defaults is None:
        defaults = _zero_counts()
    if prefix:
        print(prefix)
    counts = {}
    counts["5"] = prompt_int(
        "5xAmt (count of crafts with >=5 stickers)", defaults.get("5", 0)
    )
    counts["4"] = prompt_int(
        "4xAmt (count of crafts with >=4 stickers)", defaults.get("4", 0)
    )
    counts["3"] = prompt_int(
        "3xAmt (count of crafts with >=3 stickers)", defaults.get("3", 0)
    )
    counts["2"] = prompt_int(
        "2xAmt (count of crafts with >=2 stickers)", defaults.get("2", 0)
    )
    counts["1"] = prompt_int(
        "1xAmt (count of crafts with >=1 sticker)", defaults.get("1", 0)
    )
    return counts


# ---------- Core math ----------

def calc_exact_counts_and_flops(counts):
    c5 = counts.get("5", 0)
    c4 = counts.get("4", 0)
    c3 = counts.get("3", 0)
    c2 = counts.get("2", 0)
    c1 = counts.get("1", 0)

    e5 = max(c5, 0)
    e4 = max(c4 - c5, 0)
    e3 = max(c3 - c4, 0)
    e2 = max(c2 - c3, 0)
    e1 = max(c1 - c2, 0)

    exact_counts = {
        "5": e5,
        "4": e4,
        "3": e3,
        "2": e2,
        "1": e1,
    }

    flops = {
        "5": e5 * 5,
        "4": e4 * 4,
        "3": e3 * 3,
        "2": e2 * 2,
        "1": e1 * 1,
    }

    total_flops = sum(flops.values())
    return exact_counts, flops, total_flops


def safe_pct(part, whole):
    if whole == 0:
        return 0.0
    return (part / whole) * 100.0


# ---------- Logging ----------

def append_log(
    steamid,
    flopAmt,
    flopPerc,
    flopRank,
    exact_counts,
    totalFlop,
    total_exact_counts,
    perc_by_x,
):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(DATA_FILE, "a", encoding="utf-8") as f:
        f.write("|---------------\n")
        f.write(
            f"|{steamid} {flopAmt}/{totalFlop} Floppy Applied ({flopPerc:.2f}%) "
            f"[Rank #{flopRank}]\n"
        )
        f.write(
            f"|5x Crafts: {exact_counts['5']} "
            f"4x Crafts: {exact_counts['4']} "
            f"3x Crafts: {exact_counts['3']} "
            f"2x Crafts: {exact_counts['2']} "
            f"1x Crafts: {exact_counts['1']}\n"
        )
        f.write(
            f"|Total 5x Crafts: {total_exact_counts['5']} "
            f"Total 4x Crafts: {total_exact_counts['4']} "
            f"Total 3x Crafts: {total_exact_counts['3']} "
            f"Total 2x Crafts: {total_exact_counts['2']} "
            f"Total 1x Crafts: {total_exact_counts['1']}\n"
        )
        f.write(
            f"|% of 5x: {perc_by_x['5']:.2f}% - "
            f"% of 4x: {perc_by_x['4']:.2f}% - "
            f"% of 3x: {perc_by_x['3']:.2f}% - "
            f"% of 2x: {perc_by_x['2']:.2f}% - "
            f"% of 1x: {perc_by_x['1']:.2f}%\n"
        )
        f.write(f"|{ts}\n")
        f.write("|---------------\n")


# ---------- Graphic output ----------

def _load_courier_fonts():
    if not HAS_PIL:
        return (None, None, None)

    font_candidates = [
        "cour.ttf",
        "Courier_New.ttf",
        "Courier New.ttf",
        "Couri.ttf",
    ]
    for name in font_candidates:
        try:
            big = ImageFont.truetype(name, 40)
            med = ImageFont.truetype(name, 26)
            small = ImageFont.truetype(name, 22)
            return big, med, small
        except Exception:
            continue

    default = ImageFont.load_default()
    return default, default, default


def _layout_and_draw(
    draw,
    width,
    steamid,
    display_name,
    flopAmt,
    totalFlop,
    flopPerc,
    flopRank,
    exact_counts,
    total_exact_counts,
    perc_by_x,
    font_big,
    font_med,
    font_small,
    text_color,
    height_only=False,
):
    """
    Layout text, with per-line auto-shrink when it would wrap.
    """
    x_left = 40
    max_text_width = width - 80
    y = 40

    def make_smaller_font(base_font, factor=0.85, min_size=14):
        try:
            base_size = getattr(base_font, "size", 26)
            new_size = max(int(base_size * factor), min_size)
            font_path = getattr(base_font, "path", None)
            if font_path:
                return ImageFont.truetype(font_path, new_size)
        except Exception:
            pass
        return base_font

    def draw_wrapped(text, font, y_in):
        nonlocal draw
        x = x_left
        y_local = y_in

        bbox_full = draw.textbbox((0, 0), text, font=font)
        full_width = bbox_full[2] - bbox_full[0]
        use_font = font
        if full_width > max_text_width:
            use_font = make_smaller_font(font)

        words = text.split(" ")
        line = ""
        for word in words:
            test = line + word + " "
            bbox = draw.textbbox((0, 0), test, font=use_font)
            w = bbox[2] - bbox[0]
            if w > max_text_width and line:
                if not height_only:
                    draw.text((x, y_local), line, fill=text_color, font=use_font)
                y_local += use_font.size + 8
                line = word + " "
            else:
                line = test
        if line:
            if not height_only:
                draw.text((x, y_local), line, fill=text_color, font=use_font)
            y_local += use_font.size + 8
        return y_local

    # Header: username (steamid) or {unknown} (steamid)
    if display_name and display_name.strip():
        header_id = f"{display_name} ({steamid})"
    else:
        header_id = f"{{unknown}} ({steamid})"

    y = draw_wrapped(f"{header_id} | Rank #{flopRank}", font_big, y)
    y = draw_wrapped(f"{flopAmt}/{totalFlop} Floppy Applied ({flopPerc:.2f}%)", font_med, y)
    y += 4

    y = draw_wrapped(
        f"5x Crafts: {exact_counts['5']}   "
        f"4x Crafts: {exact_counts['4']}   "
        f"3x Crafts: {exact_counts['3']}   "
        f"2x Crafts: {exact_counts['2']}   "
        f"1x Crafts: {exact_counts['1']}",
        font_med,
        y,
    )

    y = draw_wrapped(
        f"Total 5x: {total_exact_counts['5']}   "
        f"Total 4x: {total_exact_counts['4']}   "
        f"Total 3x: {total_exact_counts['3']}   "
        f"Total 2x: {total_exact_counts['2']}   "
        f"Total 1x: {total_exact_counts['1']}",
        font_med,
        y,
    )

    y = draw_wrapped(
        f"5x: {perc_by_x['5']:.2f}%   |   "
        f"4x: {perc_by_x['4']:.2f}%   |   "
        f"3x: {perc_by_x['3']:.2f}%   |   "
        f"2x: {perc_by_x['2']:.2f}%   |   "
        f"1x: {perc_by_x['1']:.2f}%",
        font_med,
        y,
    )

    y += 10

    rows = _get_top10_rows()
    y = draw_wrapped("Top 10 Floppy Leaderboard", font_med, y)

    for rank, sid, amt, name in rows:
        marker = ">" if sid == steamid else " "
        safe_name = name.strip() if name else "{unknown}"
        row_text = f"{marker} {rank}. {safe_name} ({sid})  {amt}"
        y = draw_wrapped(row_text, font_small, y)

    y += 10

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    y = draw_wrapped(f"Generated: {ts}", font_small, y)

    return y


def generate_floppy_image(
    steamid,
    display_name,
    flopAmt,
    totalFlop,
    flopPerc,
    flopRank,
    exact_counts,
    total_exact_counts,
    perc_by_x,
):
    if not HAS_PIL:
        print("Pillow (PIL) not installed, cannot generate image.")
        return None

    bg_color = (0x38, 0x19, 0x5e)
    text_color = (0x92, 0x67, 0xc7)

    width = 1100
    min_height = 600

    font_big, font_med, font_small = _load_courier_fonts()

    # First pass for height
    tmp_img = Image.new("RGBA", (width, 10), bg_color)
    tmp_draw = ImageDraw.Draw(tmp_img)
    bottom_y = _layout_and_draw(
        tmp_draw,
        width,
        steamid,
        display_name,
        flopAmt,
        totalFlop,
        flopPerc,
        flopRank,
        exact_counts,
        total_exact_counts,
        perc_by_x,
        font_big,
        font_med,
        font_small,
        text_color,
        height_only=True,
    )

    height = max(min_height, bottom_y + 40)

    # Second pass actual draw
    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    _layout_and_draw(
        draw,
        width,
        steamid,
        display_name,
        flopAmt,
        totalFlop,
        flopPerc,
        flopRank,
        exact_counts,
        total_exact_counts,
        perc_by_x,
        font_big,
        font_med,
        font_small,
        text_color,
        height_only=False,
    )

    # Place jimy bottom-right first (clamped)
    jx = jy = None
    margin = 40

    if os.path.exists(JIMY_ICON):
        try:
            jimy = Image.open(JIMY_ICON).convert("RGBA")
            max_w = 180
            scale = min(max_w / jimy.width, 1.0)
            new_size = (int(jimy.width * scale), int(jimy.height * scale))
            jimy = jimy.resize(new_size, Image.LANCZOS)

            # Tint overlay
            r, g, b, a = jimy.split()
            tinted = Image.new("RGBA", jimy.size, text_color + (0,))
            tinted.putalpha(a.point(lambda v: int(v * 0.5)))
            jimy_tinted = tinted

            jx = max(margin, width - new_size[0] - margin)
            jy = max(margin, height - new_size[1] - margin)

            img.paste(jimy_tinted, (jx, jy), jimy_tinted)
        except Exception as e:
            print(f"Failed to load jimy icon: {e}")

    # Place floppy image above jimy, clamped
    if os.path.exists(FLOPPY_ICON):
        try:
            icon = Image.open(FLOPPY_ICON).convert("RGBA")
            max_icon_width = 260
            scale = min(max_icon_width / icon.width, 1.0)
            new_size = (int(icon.width * scale), int(icon.height * scale))
            icon = icon.resize(new_size, Image.LANCZOS)

            alpha = icon.split()[3]
            alpha = alpha.point(lambda a: int(a * 0.7))
            icon.putalpha(alpha)

            if jx is not None and jy is not None:
                icon_x = jx
                icon_y = jy - new_size[1] - 20
            else:
                icon_x = width - new_size[0] - margin
                icon_y = height - new_size[1] - margin

            icon_x = max(margin, min(icon_x, width - new_size[0] - margin))

            img.paste(icon, (icon_x, icon_y), icon)
        except Exception as e:
            print(f"Failed to load floppy icon: {e}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"floppy_{steamid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    img.save(out_path)
    print(f"Image saved to: {out_path}")
    return out_path


# ---------- Main flow ----------

def main():
    settings = load_settings()

    total_order = settings.get("total_calc_order", "after").lower()
    if total_order not in ("before", "after"):
        total_order = "after"

    steamid = prompt_steam_id(settings)

    known_ids = load_known_ids()
    if steamid not in known_ids:
        known_ids.add(steamid)
        save_known_ids(known_ids)

    last_current_map = load_last_current_counts()
    current_defaults = last_current_map.get(steamid, _zero_counts())
    total_defaults = load_last_total_counts()

    if total_order == "before":
        print("\nEnter TOTAL ever-applied counts (inclusive, across all known id64s):")
        total_counts = prompt_counts("[TOTAL]", defaults=total_defaults)
        print("\nEnter CURRENT counts for this Steam ID (inclusive):")
        current_counts = prompt_counts("[CURRENT]", defaults=current_defaults)
    else:
        print("\nEnter CURRENT counts for this Steam ID (inclusive):")
        current_counts = prompt_counts("[CURRENT]", defaults=current_defaults)
        print("\nEnter TOTAL ever-applied counts (inclusive, across all known id64s):")
        total_counts = prompt_counts("[TOTAL]", defaults=total_defaults)

    last_current_map[steamid] = current_counts
    save_last_current_counts(last_current_map)
    save_last_total_counts(total_counts)

    exact_current, flops_current, flopAmt = calc_exact_counts_and_flops(current_counts)
    exact_total, flops_total, totalFlop = calc_exact_counts_and_flops(total_counts)

    flopPerc = safe_pct(flopAmt, totalFlop)

    perc_by_x = {}
    for x in ("5", "4", "3", "2", "1"):
        perc_by_x[x] = safe_pct(flops_current[x], flopAmt)

    flopRank, top_dict = update_topflop_and_get_rank(steamid, flopAmt, settings=settings)
    display_name = top_dict.get(steamid, {}).get("name") or "{unknown}"

    print("\n--- Summary ---")
    print(f"Steam ID64: {steamid}")
    print(f"Username (from Steam or fallback): {display_name}")
    print(f"flopAmt (this ID): {flopAmt}")
    print(f"totalFlop (all IDs): {totalFlop}")
    print(f"flopPerc (this ID vs total): {flopPerc:.2f}%")
    print(f"flopRank (leaderboard): #{flopRank}")

    print("\nExact craft counts (this ID):")
    for x in ("5", "4", "3", "2", "1"):
        print(f"  {x}x exact crafts: {exact_current[x]} (flops: {flops_current[x]})")

    print("\nExact craft counts (TOTAL):")
    for x in ("5", "4", "3", "2", "1"):
        print(f"  total{x}x exact crafts: {exact_total[x]} (flops: {flops_total[x]})")

    print("\nComposition of flopAmt by band (this ID):")
    for x in ("5", "4", "3", "2", "1"):
        print(f"  {x}x band: {perc_by_x[x]:.2f}% of flopAmt")

    append_log(
        steamid=steamid,
        flopAmt=flopAmt,
        flopPerc=flopPerc,
        flopRank=flopRank,
        exact_counts=exact_current,
        totalFlop=totalFlop,
        total_exact_counts=exact_total,
        perc_by_x=perc_by_x,
    )

    print(f"\nLogged to {DATA_FILE}. Leaderboard in {TOPFLOP_FILE}.")

    if HAS_PIL:
        gen = input("Generate image for this result? [y/N]: ").strip().lower()
        if gen == "y":
            generate_floppy_image(
                steamid=steamid,
                display_name=display_name,
                flopAmt=flopAmt,
                totalFlop=totalFlop,
                flopPerc=flopPerc,
                flopRank=flopRank,
                exact_counts=exact_current,
                total_exact_counts=exact_total,
                perc_by_x=perc_by_x,
            )
    else:
        print("Pillow is not installed; skipping image generation.")


if __name__ == "__main__":
    main()
