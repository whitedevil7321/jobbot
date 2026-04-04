"""
Run this once to generate icon16.png, icon48.png, icon128.png for the extension.
Requires: pip install Pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

SIZES = [16, 48, 128]
OUT_DIR = os.path.dirname(__file__)

BG      = (17, 24, 39)      # #111827
ACCENT  = (124, 58, 237)    # #7c3aed
WHITE   = (255, 255, 255)

def make_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rect background
    r = size // 5
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    # Purple circle accent
    pad = size // 6
    draw.ellipse([pad, pad, size - pad, size - pad], fill=ACCENT)

    # Lightning bolt / text
    cx, cy = size // 2, size // 2
    bolt_w = max(2, size // 10)
    # Simple lightning bolt shape
    pts = [
        (cx + bolt_w, cy - size // 4),
        (cx - bolt_w // 2, cy),
        (cx + bolt_w // 2, cy),
        (cx - bolt_w, cy + size // 4),
        (cx + bolt_w // 2, cy - bolt_w // 2),
        (cx - bolt_w // 2, cy - bolt_w // 2),
    ]
    draw.polygon([
        (cx + bolt_w, cy - size // 4),
        (cx - bolt_w, cy + size // 8),
        (cx, cy + size // 8),
        (cx - bolt_w, cy + size // 4),
        (cx + bolt_w, cy - size // 8),
        (cx, cy - size // 8),
    ], fill=WHITE)

    path = os.path.join(OUT_DIR, f'icon{size}.png')
    img.save(path, 'PNG')
    print(f'Created {path}')

if __name__ == '__main__':
    for s in SIZES:
        make_icon(s)
    print('Done! All icons generated.')
