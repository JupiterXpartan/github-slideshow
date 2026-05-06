"""
Generates Antheneo app icons in multiple sizes.
Requires: pip install Pillow
Output:   assets/icon.png (256x256), assets/icon.ico (Windows multi-size),
          assets/icon.icns placeholder note, assets/icon.svg
"""

import math
from pathlib import Path

OUT = Path(__file__).parent


def _draw_icon(size: int):
    from PIL import Image, ImageDraw, ImageFont

    BG      = (13,  17,  23,  255)   # #0d1117
    CYAN    = (0,   212, 212, 255)   # #00d4d4
    CYAN_DIM= (0,   127, 127, 200)   # dimmed cyan
    WHITE   = (230, 237, 243, 255)

    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = size * 0.04

    # ── Rounded-rect background ──────────────────────────────────────────
    r = size * 0.18
    draw.rounded_rectangle([pad, pad, size - pad, size - pad],
                            radius=r, fill=BG)

    # ── Shield outline ───────────────────────────────────────────────────
    cx, cy = size / 2, size / 2
    sw = size * 0.72          # shield width
    sh = size * 0.80          # shield height
    sx = cx - sw / 2
    sy = cy - sh / 2 + size * 0.02

    # Shield polygon: top-left, top-right, right-mid, bottom-tip, left-mid
    tip_y  = sy + sh
    mid_y  = sy + sh * 0.62
    pts = [
        (sx,         sy + sh * 0.18),   # left shoulder
        (cx,         sy),               # top centre
        (sx + sw,    sy + sh * 0.18),   # right shoulder
        (sx + sw,    mid_y),            # right mid
        (cx,         tip_y),            # bottom tip
        (sx,         mid_y),            # left mid
    ]
    draw.polygon(pts, fill=CYAN_DIM)
    lw = max(2, int(size * 0.025))
    draw.polygon(pts, outline=CYAN, width=lw)

    # ── "A" lettermark ───────────────────────────────────────────────────
    # Draw as lines so we don't need a font file
    a_h   = sh * 0.48
    a_w   = sw * 0.46
    ax    = cx - a_w / 2
    ay    = cy - a_h / 2 - sh * 0.04
    lw2   = max(3, int(size * 0.055))

    # Left leg
    draw.line([(ax, ay + a_h), (cx, ay)], fill=WHITE, width=lw2)
    # Right leg
    draw.line([(cx, ay), (ax + a_w, ay + a_h)], fill=WHITE, width=lw2)
    # Crossbar
    bar_y = ay + a_h * 0.56
    bar_margin = a_w * 0.22
    draw.line([(ax + bar_margin, bar_y),
               (ax + a_w - bar_margin, bar_y)],
              fill=CYAN, width=lw2)

    # ── Cyan dot at shield tip ───────────────────────────────────────────
    dr = max(3, int(size * 0.04))
    draw.ellipse([(cx - dr, tip_y - dr * 2.4 - dr),
                  (cx + dr, tip_y - dr * 2.4 + dr)],
                 fill=CYAN)

    return img


def generate_png(size=256) -> Path:
    img  = _draw_icon(size)
    path = OUT / "icon.png"
    img.save(path, "PNG")
    print(f"  icon.png ({size}×{size}) → {path}")
    return path


def generate_ico() -> Path:
    """Multi-resolution .ico for Windows (16, 32, 48, 64, 128, 256)."""
    sizes   = [16, 32, 48, 64, 128, 256]
    images  = [_draw_icon(s) for s in sizes]
    path    = OUT / "icon.ico"
    images[0].save(path, format="ICO", append_images=images[1:],
                   sizes=[(s, s) for s in sizes])
    print(f"  icon.ico (multi-size) → {path}")
    return path


def generate_svg() -> Path:
    """Simple SVG version."""
    svg = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="46" fill="#0d1117"/>
  <polygon points="128,28 210,66 210,148 128,228 46,148 46,66"
           fill="#007f7f" stroke="#00d4d4" stroke-width="6"/>
  <line x1="82"  y1="196" x2="128" y2="80"  stroke="#e6edf3" stroke-width="14" stroke-linecap="round"/>
  <line x1="128" y1="80"  x2="174" y2="196" stroke="#e6edf3" stroke-width="14" stroke-linecap="round"/>
  <line x1="96"  y1="152" x2="160" y2="152" stroke="#00d4d4" stroke-width="14" stroke-linecap="round"/>
  <circle cx="128" cy="210" r="8" fill="#00d4d4"/>
</svg>"""
    path = OUT / "icon.svg"
    path.write_text(svg)
    print(f"  icon.svg → {path}")
    return path


if __name__ == "__main__":
    print("Generating Antheneo icons…")
    try:
        generate_png(256)
        generate_ico()
    except ImportError:
        print("  Pillow not installed — skipping raster icons.")
        print("  Install with: pip install Pillow")
    generate_svg()
    print("Done.")
