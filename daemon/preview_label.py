#!/usr/bin/env python3
"""
Label style preview — generates a label image and opens it.
Edit config.json to change styles, then run: python preview_label.py
"""

import os, sys, json
from pathlib import Path

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import (
        SquareModuleDrawer, RoundedModuleDrawer,
        CircleModuleDrawer, GappedSquareModuleDrawer,
        HorizontalBarsDrawer, VerticalBarsDrawer,
    )
    from PIL import Image, ImageDraw, ImageFont
    from brother_ql.labels import ALL_LABELS
except ImportError as e:
    print(f"Missing dependency: {e}\nRun: pip install -r requirements.txt")
    sys.exit(1)

BASE = Path(__file__).parent

# ── Only edit this ────────────────────────────────────────────────────────────
TEST_VALUE = "M0L0_10"   # value to preview
# ─────────────────────────────────────────────────────────────────────────────

cfg = json.loads((BASE / "config.json").read_text())

STYLE_MAP = {
    "square":  SquareModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "circle":  CircleModuleDrawer,
    "gapped":  GappedSquareModuleDrawer,
    "hbars":   HorizontalBarsDrawer,
    "vbars":   VerticalBarsDrawer,
}
EC_MAP = {"L": qrcode.constants.ERROR_CORRECT_L, "M": qrcode.constants.ERROR_CORRECT_M,
          "Q": qrcode.constants.ERROR_CORRECT_Q, "H": qrcode.constants.ERROR_CORRECT_H}


QR_LIGHT    = cfg.get("qr_light", "#ffffff")

FONT_PATHS  = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial_Bold.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

DPI = 300
def mm(v): return round(v * DPI / 25.4)

def get_label_px(label_type):
    for label in ALL_LABELS:
        if label.identifier == label_type:
            return label.dots_printable
    raise ValueError(f"Unknown label type: {label_type}")

def load_font(size_px):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size_px)
            except Exception:
                pass
    return ImageFont.load_default()

def make_preview(value):
    margin_mm        = cfg.get("margin_mm", 3)
    qr_fraction      = cfg.get("qr_fraction", 1.0)
    qr_border        = cfg.get("qr_border", 1)
    qr_dark          = cfg.get("qr_dark", "#000000")
    qr_light         = cfg.get("qr_light", "#ffffff")
    error_correction = EC_MAP.get(cfg.get("qr_error_correction", "M"), qrcode.constants.ERROR_CORRECT_M)
    style_drawer     = STYLE_MAP.get(cfg.get("qr_style", "square"), SquareModuleDrawer)()
    show_text        = cfg.get("show_text", True)
    font_size_frac   = cfg.get("font_size_fraction", 0.45)
    gap_mm           = cfg.get("gap_mm", 2)

    w, h = get_label_px(cfg.get("label_type", "62x29"))
    mg = mm(margin_mm)
    img = Image.new("RGB", (w, h), qr_light)
    draw = ImageDraw.Draw(img)

    content_h = h - 2 * mg
    content_w = w - 2 * mg
    qr_size   = round(content_h * qr_fraction)

    # Build QR first to get module count, then render at exact pixel size
    qr = qrcode.QRCode(error_correction=error_correction, box_size=1, border=qr_border)
    qr.add_data(value)
    qr.make(fit=True)
    n_modules = qr.modules_count + 2 * qr_border
    box_size = max(1, qr_size // n_modules)
    qr2 = qrcode.QRCode(error_correction=error_correction, box_size=box_size, border=qr_border)
    qr2.add_data(value)
    qr2.make(fit=True)
    qr_img = qr2.make_image(
        image_factory=StyledPilImage,
        module_drawer=style_drawer,
    ).convert("RGB")
    qr_img = qr_img.crop((0, 0, min(qr_size, qr_img.width), min(qr_size, qr_img.height)))
    paste_img = Image.new("RGB", (qr_size, qr_size), qr_light)
    paste_img.paste(qr_img, (0, 0))
    img.paste(paste_img, (mg, mg))

    if show_text:
        gap = mm(gap_mm)
        text_x = mg + qr_size + gap
        text_w = content_w - qr_size - gap
        font_px = max(10, round(content_h * font_size_frac))
        font = load_font(font_px)

        words = str(value).split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= text_w:
                line = test
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)

        line_h = font_px + mm(1)
        total_h = len(lines) * line_h
        text_y = mg + max(0, (content_h - total_h) // 2)
        for ln in lines:
            draw.text((text_x, text_y), ln, fill=qr_dark, font=font)
            text_y += line_h

    return img

if __name__ == "__main__":
    img = make_preview(TEST_VALUE)

    # Full-res (300 DPI) — for print accuracy
    out = Path(__file__).parent / "preview_label.png"
    img.save(out, dpi=(300, 300))
    print(f"Saved full-res : {out}  ({img.width}x{img.height} px)")

    # True-size screen preview (96 DPI equivalent — actual label size on screen)
    SCREEN_DPI = 96
    scale = SCREEN_DPI / 300
    screen_w = max(1, round(img.width  * scale))
    screen_h = max(1, round(img.height * scale))
    screen_img = img.resize((screen_w, screen_h), Image.LANCZOS)
    out_screen = Path(__file__).parent / "preview_label_actual_size.png"
    screen_img.save(out_screen, dpi=(SCREEN_DPI, SCREEN_DPI))
    print(f"Saved true-size: {out_screen}  ({screen_w}x{screen_h} px  ≈ actual 62×29mm on screen)")

    os.startfile(out_screen)  # open the true-size one
