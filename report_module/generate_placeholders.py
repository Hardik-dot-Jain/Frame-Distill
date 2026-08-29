"""
Generates 24 placeholder frame PNGs (320x240) with varied gradient colors.
Saves to: data/dev_mock/sample_frames/
Run from the repo root: python report_module/generate_placeholders.py
"""

import os
import struct
import zlib
import math

OUTPUT_DIR = os.path.join("data", "dev_mock", "sample_frames")
WIDTH, HEIGHT = 320, 240

# 24 unique color palettes: (top_color_rgb, bottom_color_rgb)
PALETTES = [
    ((30,  27,  75),  (99,  102, 241)),  # 001 – deep indigo
    ((15, 23,  42),   (56,  189, 248)),  # 002 – midnight to cyan
    ((4,  120,  87),  (110, 231, 183)),  # 003 – forest green
    ((124, 45,  18),  (253, 186, 116)),  # 004 – burnt orange
    ((88,  28, 135),  (216, 180, 254)),  # 005 – purple dusk
    ((30,  58,  138), (147, 197, 253)),  # 006 – ocean blue
    ((6,   78,  59),  (52,  211, 153)),  # 007 – emerald
    ((127, 29,  29),  (252, 165, 165)),  # 008 – rose red
    ((23,  37,  84),  (165, 180, 252)),  # 009 – navy violet
    ((78,  33,   0),  (251, 146,  60)),  # 010 – amber ember
    ((17,  24,  39),  (209, 213, 219)),  # 011 – dark slate to silver
    ((3,   105, 161), (186, 230, 253)),  # 012 – sky teal
    ((55,  14,  70),  (249, 168, 212)),  # 013 – magenta bloom
    ((6,   95,  70),  (167, 243, 208)),  # 014 – mint
    ((30,  27,  75),  (129, 140, 248)),  # 015 – periwinkle
    ((17,  94,  89),  (94,  234, 212)),  # 016 – aquamarine
    ((110,  0,   0),  (254, 202, 202)),  # 017 – crimson fade
    ((32,  45,   0),  (190, 242, 100)),  # 018 – lime glow
    ((8,   51, 112),  (147, 197, 253)),  # 019 – cobalt
    ((64,  0,   55),  (240, 171, 252)),  # 020 – fuchsia
    ((7,   89,  133), (103, 232, 249)),  # 021 – ice blue
    ((54,  7,   7),   (253, 224, 132)),  # 022 – golden dusk
    ((1,   60,  32),  (74,  222, 128)),  # 023 – verdant
    ((23,  37,  84),  (252, 231, 121)),  # 024 – midnight gold
]


def _encode_png(width, height, pixels):
    """Pure-stdlib minimal PNG encoder (RGB, 8-bit)."""
    def chunk(name, data):
        raw = name + data
        return (struct.pack('>I', len(data)) + raw +
                struct.pack('>I', zlib.crc32(raw) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)

    # Build raw image data: filter byte 0 + RGB rows
    raw_rows = []
    for y in range(height):
        row = bytearray([0])          # filter type: None
        for x in range(width):
            row += bytearray(pixels[y][x])
        raw_rows.append(bytes(row))

    idat_data = zlib.compress(b''.join(raw_rows), 9)

    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', idat_data) +
            chunk(b'IEND', b''))


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generate_frame(path, top_color, bottom_color, frame_num):
    pixels = []
    for y in range(HEIGHT):
        row = []
        t_vert = y / (HEIGHT - 1)
        for x in range(WIDTH):
            t_horiz = x / (WIDTH - 1)
            # Blend vertically then add a slight diagonal shimmer
            shimmer = 0.08 * math.sin(t_horiz * math.pi * 3 + frame_num * 0.7)
            t = max(0.0, min(1.0, t_vert + shimmer))
            row.append(lerp_color(top_color, bottom_color, t))
        pixels.append(row)

    with open(path, 'wb') as f:
        f.write(_encode_png(WIDTH, HEIGHT, pixels))


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for i, (top, bottom) in enumerate(PALETTES, start=1):
        filename = f"frame_{i:04d}.png"
        filepath = os.path.join(OUTPUT_DIR, filename)
        generate_frame(filepath, top, bottom, i)
        print(f"  [{i:02d}/24] {filename}")
    print(f"\n[OK] 24 placeholder frames saved to: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
