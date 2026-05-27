#!/usr/bin/env python3
"""
QR Label Print Daemon
Polls a Google Sheet for checked checkboxes, generates QR labels,
and prints silently to a Brother QL printer — no browser, no dialog.
"""

import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import (
        SquareModuleDrawer, RoundedModuleDrawer, CircleModuleDrawer,
        GappedSquareModuleDrawer, HorizontalBarsDrawer, VerticalBarsDrawer,
    )
    from PIL import Image, ImageDraw, ImageFont
    from brother_ql.conversion import convert
    from brother_ql.backends.helpers import send
    from brother_ql.raster import BrotherQLRaster
    from brother_ql.labels import ALL_LABELS
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run:  pip install -r requirements.txt")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
def load_config():
    path = BASE / "config.json"
    if not path.exists():
        print(f"config.json not found at {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)

# ── Google Sheets ─────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheets_service():
    token_path = BASE / "token.json"
    creds_path = BASE / "credentials.json"
    if not creds_path.exists():
        print(f"credentials.json not found at {creds_path}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        print("(Create an OAuth 2.0 Client ID for a Desktop app)")
        sys.exit(1)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("sheets", "v4", credentials=creds).spreadsheets()

def col_letter_to_index(letter):
    """'A' → 0, 'B' → 1, …"""
    result = 0
    for ch in letter.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1

def get_pending_rows(service, cfg):
    """Return list of (row_1based, qr_value) where the print checkbox is checked."""
    range_name = f"{cfg['sheet_name']}!A2:Z"
    result = (
        service.values()
        .get(
            spreadsheetId=cfg["spreadsheet_id"],
            range=range_name,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    rows = result.get("values", [])
    qi = col_letter_to_index(cfg["qr_col"])
    pi = col_letter_to_index(cfg["print_col"])

    pending = []
    for i, row in enumerate(rows):
        if len(row) > pi and row[pi] is True:
            qr_val = str(row[qi]) if len(row) > qi and row[qi] != "" else None
            if qr_val:
                pending.append((i + 2, qr_val))  # 1-based row index
    return pending

def uncheck_row(service, cfg, row_index):
    range_name = f"{cfg['sheet_name']}!{cfg['print_col']}{row_index}"
    service.values().update(
        spreadsheetId=cfg["spreadsheet_id"],
        range=range_name,
        valueInputOption="RAW",
        body={"values": [[False]]},
    ).execute()

# ── Label image ───────────────────────────────────────────────────────────────
DPI = 300
MM_TO_PX = DPI / 25.4

def mm(val):
    return round(val * MM_TO_PX)

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


    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial_Bold.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

def load_font(size_px):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size_px)
            except Exception:
                pass
    return ImageFont.load_default()

def get_label_px(label_type):
    """Return (width_px, height_px) from brother_ql's label definition."""
    for label in ALL_LABELS:
        if label.identifier == label_type:
            return label.dots_printable
    raise ValueError(f"Unknown label type: {label_type}")

def make_label_image(value, width_px, height_px, cfg):
    margin_mm         = cfg.get("margin_mm", 3)
    qr_fraction       = cfg.get("qr_fraction", 1.0)
    qr_border         = cfg.get("qr_border", 1)
    qr_dark           = cfg.get("qr_dark", "#000000")
    qr_light          = cfg.get("qr_light", "#ffffff")
    error_correction  = EC_MAP.get(cfg.get("qr_error_correction", "M"), qrcode.constants.ERROR_CORRECT_M)
    style_drawer      = STYLE_MAP.get(cfg.get("qr_style", "square"), SquareModuleDrawer)()
    show_text         = cfg.get("show_text", True)
    font_size_frac    = cfg.get("font_size_fraction", 0.45)
    gap_mm            = cfg.get("gap_mm", 2)

    w, h = width_px, height_px
    mg = mm(margin_mm)
    img = Image.new("RGB", (w, h), qr_light)
    draw = ImageDraw.Draw(img)

    content_h = h - 2 * mg
    content_w = w - 2 * mg
    qr_size   = round(content_h * qr_fraction)

    # ── QR code — crisp, no resize ────────────────────────────────────────────
    qr = qrcode.QRCode(error_correction=error_correction, box_size=1, border=qr_border)
    qr.add_data(value)
    qr.make(fit=True)
    n_modules = qr.modules_count + 2 * qr_border
    box_size  = max(1, qr_size // n_modules)
    qr2 = qrcode.QRCode(error_correction=error_correction, box_size=box_size, border=qr_border)
    qr2.add_data(value)
    qr2.make(fit=True)
    qr_img = qr2.make_image(image_factory=StyledPilImage, module_drawer=style_drawer).convert("RGB")
    qr_img = qr_img.crop((0, 0, min(qr_size, qr_img.width), min(qr_size, qr_img.height)))
    canvas = Image.new("RGB", (qr_size, qr_size), qr_light)
    canvas.paste(qr_img, (0, 0))
    img.paste(canvas, (mg, mg))

    # ── Text ──────────────────────────────────────────────────────────────────
    if show_text:
        gap    = mm(gap_mm)
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
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)

        line_h  = font_px + mm(1)
        total_h = len(lines) * line_h
        text_y  = mg + max(0, (content_h - total_h) // 2)
        for ln in lines:
            draw.text((text_x, text_y), ln, fill=qr_dark, font=font)
            text_y += line_h

    return img

# ── Brother QL printing ───────────────────────────────────────────────────────
def print_label(img, cfg):
    model       = cfg["model"]          # e.g. "QL-1080N"
    label_type  = cfg["label_type"]     # e.g. "62x29"
    printer_uri = cfg["printer_uri"]    # e.g. "tcp://192.168.1.100"

    backend = "network" if printer_uri.startswith("tcp://") else "pyusb"

    qlr = BrotherQLRaster(model)
    qlr.exception_on_warning = True

    instructions = convert(
        qlr=qlr,
        images=[img],
        label=label_type,
        rotate="0",
        threshold=70.0,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=True,
    )

    send(
        instructions=instructions,
        printer_identifier=printer_uri,
        backend_identifier=backend,
        blocking=True,
    )

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    service = get_sheets_service()

    print("QR Print Daemon running")
    print(f"  Sheet  : {cfg['spreadsheet_id']}")
    print(f"  Printer: {cfg['printer_uri']}  model={cfg['model']}")
    print(f"  Poll   : every {cfg['poll_interval_seconds']}s")
    print("  Press Ctrl+C to stop\n")

    prev_checked = None  # None = first poll (snapshot only, no printing)

    while True:
        try:
            pending = get_pending_rows(service, cfg)
            current_checked = {row for row, _ in pending}

            if prev_checked is None:
                # First poll: snapshot existing checked boxes, skip them
                prev_checked = current_checked
                n = len(current_checked)
                if n:
                    print(f"[startup] Skipping {n} already-checked row(s): {sorted(current_checked)}")
            else:
                # Only print rows that are newly checked since last poll
                new_rows = [(r, v) for r, v in pending if r not in prev_checked]
                for row_index, qr_value in new_rows:
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"[{ts}] Row {row_index} → {qr_value!r}", end=" ", flush=True)
                    try:
                        w_px, h_px = get_label_px(cfg["label_type"])
                        img = make_label_image(qr_value, w_px, h_px, cfg)
                        print_label(img, cfg)
                        print("✓")
                    except Exception as e:
                        print(f"✗  {e}")

                prev_checked = current_checked

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Poll error: {e}")

        time.sleep(cfg["poll_interval_seconds"])

if __name__ == "__main__":
    main()
