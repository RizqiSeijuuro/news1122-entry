#!/usr/bin/env python3
"""
make.fun bounty "news-image-20261122"
Renders a 1024x1024 PNG summarizing world news of 22 November 2026.

Standard-library only (zlib + struct for a minimal PNG encoder, no network,
no third-party image libraries). Output is fully deterministic: same input
data always produces byte-identical PNG bytes.
"""

import os
import struct
import zlib

# ---------------------------------------------------------------------------
# Canvas / palette
# ---------------------------------------------------------------------------

WIDTH = 1024
HEIGHT = 1024

NAVY_BG = (10, 14, 30)
CARD_BG = (19, 26, 48)
TITLE_BAR = (14, 19, 38)
WHITE = (240, 244, 252)
DIM = (150, 165, 195)
GOLD = (245, 196, 83)

RED = (235, 86, 86)
ORANGE = (240, 150, 70)
CYAN = (90, 200, 220)
PURPLE = (175, 120, 230)
GREEN = (110, 210, 150)
BLUE = (100, 150, 240)

# ---------------------------------------------------------------------------
# Minimal 5x7 bitmap font (rows top->bottom, 5 bits per row, '1' = pixel on)
# ---------------------------------------------------------------------------

FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "11001", "10101", "10011", "10011", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "01010", "00100", "00100", "00100", "01010", "10001"],
    "Y": ["10001", "01010", "00100", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00010", "00100", "01000", "10000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00010", "01100", "00010", "00001", "11110"],
    "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "00110", "00100", "01000"],
    "'": ["01100", "01100", "00100", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "$": ["00100", "01111", "10100", "01110", "00101", "11110", "00100"],
    "%": ["11001", "11010", "00100", "01000", "00110", "01011", "10011"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
}

FONT_W = 5
FONT_H = 7
CHAR_ADVANCE = 6  # 5px glyph + 1px spacing, multiplied by scale when drawing


# ---------------------------------------------------------------------------
# Framebuffer drawing primitives
# ---------------------------------------------------------------------------

def make_canvas(w, h, color):
    row = bytes(color) * w
    return bytearray(row * h)


def set_pixel(buf, w, h, x, y, color):
    if 0 <= x < w and 0 <= y < h:
        i = (y * w + x) * 3
        buf[i] = color[0]
        buf[i + 1] = color[1]
        buf[i + 2] = color[2]


def fill_rect(buf, w, h, x0, y0, x1, y1, color):
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(w, x1)
    y1 = min(h, y1)
    if x0 >= x1 or y0 >= y1:
        return
    row = bytes(color) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * w + x0) * 3
        buf[i:i + len(row)] = row


def fill_circle(buf, w, h, cx, cy, r, color):
    r2 = r * r
    for y in range(cy - r, cy + r + 1):
        if y < 0 or y >= h:
            continue
        dy = y - cy
        span = int((r2 - dy * dy) ** 0.5) if r2 >= dy * dy else -1
        if span < 0:
            continue
        x0 = max(0, cx - span)
        x1 = min(w, cx + span + 1)
        if x0 >= x1:
            continue
        row = bytes(color) * (x1 - x0)
        i = (y * w + x0) * 3
        buf[i:i + len(row)] = row


def fill_triangle(buf, w, h, p0, p1, p2, color):
    xs = (p0[0], p1[0], p2[0])
    ys = (p0[1], p1[1], p2[1])
    y_min = max(0, min(ys))
    y_max = min(h - 1, max(ys))

    def edge(ax, ay, bx, by, px, py):
        return (bx - ax) * (py - ay) - (by - ay) * (px - ax)

    x_min = max(0, min(xs))
    x_max = min(w - 1, max(xs))
    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            d1 = edge(p0[0], p0[1], p1[0], p1[1], x, y)
            d2 = edge(p1[0], p1[1], p2[0], p2[1], x, y)
            d3 = edge(p2[0], p2[1], p0[0], p0[1], x, y)
            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            if not (has_neg and has_pos):
                set_pixel(buf, w, h, x, y, color)


def draw_char(buf, w, h, ch, x, y, color, scale):
    glyph = FONT.get(ch.upper())
    if glyph is None:
        return
    for row in range(FONT_H):
        bits = glyph[row]
        for col in range(FONT_W):
            if bits[col] == "1":
                fill_rect(
                    buf, w, h,
                    x + col * scale, y + row * scale,
                    x + (col + 1) * scale, y + (row + 1) * scale,
                    color,
                )


def text_width(s, scale):
    return len(s) * CHAR_ADVANCE * scale


def draw_text(buf, w, h, s, x, y, color, scale):
    cx = x
    for ch in s:
        draw_char(buf, w, h, ch, cx, y, color, scale)
        cx += CHAR_ADVANCE * scale


# ---------------------------------------------------------------------------
# PNG encoder (signature + IHDR + IDAT + IEND), stdlib only
# ---------------------------------------------------------------------------

def _chunk(tag, data):
    out = struct.pack(">I", len(data))
    out += tag
    out += data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def encode_png(buf, w, h):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    ihdr_chunk = _chunk(b"IHDR", ihdr)

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter type 0 (none) for every scanline
        start = y * stride
        raw.extend(buf[start:start + stride])

    compressed = zlib.compress(bytes(raw), 9)
    idat_chunk = _chunk(b"IDAT", compressed)
    iend_chunk = _chunk(b"IEND", b"")

    return sig + ihdr_chunk + idat_chunk + iend_chunk


# ---------------------------------------------------------------------------
# Content: five real 22 Nov 2026 world-news stories + a briefing card
# ---------------------------------------------------------------------------

STORIES = [
    {
        "accent": RED,
        "icon": "triangle",
        "title": "BALTIC SPILLOVER",
        "lines": [
            "RUSSIAN SHIP SPARTA II HIT BY",
            "UKRAINE DRONE, SET ABLAZE, PM",
            "WARNS WAR IS 'SPILLING OVER'",
        ],
    },
    {
        "accent": ORANGE,
        "icon": "rect",
        "title": "KRYVYI RIH ATTACK",
        "lines": [
            "RUSSIAN MISSILES AND ROCKETS",
            "HIT ZELENSKYY HOMETOWN, KILL 2",
            "RESPONDERS HIT IN FOLLOW-UP",
        ],
    },
    {
        "accent": CYAN,
        "icon": "circle",
        "title": "GULF INTERCEPTIONS",
        "lines": [
            "SAUDI ARABIA AND BAHRAIN STOP",
            "HOUTHI, IRANIAN MISSILES AND",
            "DRONES AMID GULF TENSIONS",
        ],
    },
    {
        "accent": PURPLE,
        "icon": "triangle",
        "title": "IRAN VS US SIEGE",
        "lines": [
            "IRAN DEPUTY FM CALLS US SIEGE",
            "AN 'ACT OF WAR', VOWS TO BREAK",
            "THE ECONOMIC BLOCKADE",
        ],
    },
    {
        "accent": GREEN,
        "icon": "rect",
        "title": "NUCLEAR DIPLOMACY",
        "lines": [
            "TRUMP: FUTURE IRAN NUKE DEAL",
            "MUST BE PERMANENT TO STOP",
            "TEHRAN GETTING THE BOMB",
        ],
    },
    {
        "accent": BLUE,
        "icon": "circle",
        "title": "GLOBAL BRIEFING",
        "lines": [
            "FIVE FLASHPOINTS, ONE DAY",
            "22 NOVEMBER 2026",
            "COMPILED FROM WORLD WIRE NEWS",
        ],
    },
]


# ---------------------------------------------------------------------------
# Layout math (computed once, verified with asserts before any text is drawn)
# ---------------------------------------------------------------------------

MARGIN = 20
GUTTER = 20
TITLE_BAR_H = 100
GRID_TOP = TITLE_BAR_H + 20
GRID_BOTTOM = HEIGHT - MARGIN

GRID_W = WIDTH - 2 * MARGIN
GRID_H = GRID_BOTTOM - GRID_TOP

COLS = 2
ROWS = 3

CARD_W = (GRID_W - (COLS - 1) * GUTTER) // COLS
CARD_H = (GRID_H - (ROWS - 1) * GUTTER) // ROWS

ACCENT_W = 8
PAD = 14
ICON_SIZE = 40
ICON_GAP = 10

CONTENT_W = CARD_W - ACCENT_W - 2 * PAD
TITLE_SCALE = 3
CAPTION_SCALE = 2

TITLE_X_OFFSET = ICON_SIZE + ICON_GAP
TITLE_MAX_W = CONTENT_W - TITLE_X_OFFSET
TITLE_MAX_CHARS = TITLE_MAX_W // (CHAR_ADVANCE * TITLE_SCALE)

CAPTION_MAX_W = CONTENT_W
CAPTION_MAX_CHARS = CAPTION_MAX_W // (CHAR_ADVANCE * CAPTION_SCALE)

CAPTION_LINE_H = FONT_H * CAPTION_SCALE + 6

# Hard verification: every caption/title string must fit the computed budget,
# and must only use characters present in the embedded font.
_FONT_CHARS = set(FONT.keys())
for _story in STORIES:
    assert len(_story["title"]) <= TITLE_MAX_CHARS, (
        f"title too long: {_story['title']!r} "
        f"({len(_story['title'])} > {TITLE_MAX_CHARS})"
    )
    assert set(_story["title"].upper()) <= _FONT_CHARS, (
        f"title has unsupported characters: {_story['title']!r}"
    )
    for _line in _story["lines"]:
        assert len(_line) <= CAPTION_MAX_CHARS, (
            f"caption too long: {_line!r} "
            f"({len(_line)} > {CAPTION_MAX_CHARS})"
        )
        assert set(_line.upper()) <= _FONT_CHARS, (
            f"caption has unsupported characters: {_line!r}"
        )


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_icon(buf, kind, color, x, y, size):
    if kind == "circle":
        fill_circle(buf, WIDTH, HEIGHT, x + size // 2, y + size // 2, size // 2, color)
    elif kind == "rect":
        fill_rect(buf, WIDTH, HEIGHT, x, y + size // 4, x + size, y + size - size // 4, color)
    elif kind == "triangle":
        p0 = (x + size // 2, y)
        p1 = (x, y + size)
        p2 = (x + size, y + size)
        fill_triangle(buf, WIDTH, HEIGHT, p0, p1, p2, color)


def render():
    buf = make_canvas(WIDTH, HEIGHT, NAVY_BG)

    # Title bar
    fill_rect(buf, WIDTH, HEIGHT, 0, 0, WIDTH, TITLE_BAR_H, TITLE_BAR)
    fill_rect(buf, WIDTH, HEIGHT, 0, TITLE_BAR_H - 4, WIDTH, TITLE_BAR_H, GOLD)
    draw_text(buf, WIDTH, HEIGHT, "WORLD NEWS", MARGIN, 22, WHITE, 6)
    draw_text(buf, WIDTH, HEIGHT, "22 NOVEMBER 2026", MARGIN, 70, DIM, 3)

    for idx, story in enumerate(STORIES):
        row = idx // COLS
        col = idx % COLS
        card_x = MARGIN + col * (CARD_W + GUTTER)
        card_y = GRID_TOP + row * (CARD_H + GUTTER)

        fill_rect(buf, WIDTH, HEIGHT, card_x, card_y, card_x + CARD_W, card_y + CARD_H, CARD_BG)
        fill_rect(buf, WIDTH, HEIGHT, card_x, card_y, card_x + ACCENT_W, card_y + CARD_H, story["accent"])

        content_x = card_x + ACCENT_W + PAD
        content_y = card_y + PAD

        draw_icon(buf, story["icon"], story["accent"], content_x, content_y, ICON_SIZE)

        title_x = content_x + TITLE_X_OFFSET
        title_y = content_y + (ICON_SIZE - FONT_H * TITLE_SCALE) // 2
        draw_text(buf, WIDTH, HEIGHT, story["title"], title_x, title_y, WHITE, TITLE_SCALE)

        cap_y = content_y + ICON_SIZE + PAD
        for line in story["lines"]:
            draw_text(buf, WIDTH, HEIGHT, line, content_x, cap_y, DIM, CAPTION_SCALE)
            cap_y += CAPTION_LINE_H

    return buf


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    buf = render()
    png_bytes = encode_png(buf, WIDTH, HEIGHT)

    with open(out_path, "wb") as f:
        f.write(png_bytes)


if __name__ == "__main__":
    main()
