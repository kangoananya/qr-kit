# qr-kit

Lightweight tools for QR code scanning, label generation, and silent printing to a Brother QL printer — no build step, no server required for the browser tools.

## Tools

| File | Tool | Description |
|------|------|-------------|
| `index.html` | **Scanner** | Opens your device camera and decodes QR codes in real time |
| `generator.html` | **Label Generator** | Create and print QR code labels from a form |
| `daemon/` | **Print Daemon** | Python daemon — polls a Google Sheet and prints labels silently to a Brother QL printer |

## Browser Tools

### Local

Open `generator.html` directly in any browser — no server needed.

The **scanner** requires HTTPS for camera access, so it won't work over `file://`. Use a local HTTPS server instead:

```bash
npx serve .
```

### GitHub Pages (recommended)

1. Push this repo to GitHub
2. Go to **Settings → Pages**, select branch `main`, folder `/` (root), and save
3. Your tools will be live at:
   - `https://<username>.github.io/<repo>/` — Scanner
   - `https://<username>.github.io/<repo>/generator.html` — Generator

### Browser Support

| Browser | Scanner | Generator |
|---------|---------|-----------|
| Chrome 90+ / Android | ✅ Native `BarcodeDetector` | ✅ |
| iOS Safari 14.3+ | ✅ jsQR fallback | ✅ |
| Firefox | ✅ jsQR fallback | ✅ |
| Samsung Internet | ✅ jsQR fallback | ✅ |

---

## Print Daemon

Polls a Google Sheet every few seconds. When a checkbox in the configured column is ticked, it generates a QR label image and sends it directly to a Brother QL printer over the network — no browser, no print dialog.

### Requirements

- Python 3.8+
- Brother QL printer on the local network
- Google Cloud project with Sheets API enabled

### Setup

**1. Install dependencies**
```bash
cd daemon
pip install -r requirements.txt
```

**2. Google OAuth credentials**
- Go to [console.cloud.google.com](https://console.cloud.google.com) → New project → Enable **Google Sheets API**
- Credentials → **Create Credentials → OAuth 2.0 Client ID → Desktop app**
- Download the JSON → save as `daemon/credentials.json`

**3. Edit `daemon/config.json`**
```json
{
  "spreadsheet_id": "your-sheet-id-from-url",
  "sheet_name": "Sheet1",
  "qr_col": "A",
  "print_col": "B",
  "label_type": "62x29",
  "model": "QL-1060N",
  "printer_uri": "tcp://192.168.1.xxx",
  "poll_interval_seconds": 3,

  "margin_mm": 2,
  "qr_style": "square",
  "show_text": true,
  "font_size_fraction": 0.25,
  "gap_mm": 5
}
```

`qr_style` options: `square`, `rounded`, `circle`, `gapped`, `hbars`, `vbars`

**4. First run (OAuth login)**
```bash
python print_daemon.py
```
A browser tab opens — log in with your Google account. Token saved to `token.json` for all future runs.

**5. Preview label before printing**
```bash
python preview_label.py
```
Opens `preview_label_actual_size.png` at true label size (62×29 mm equivalent on screen).

**6. Keep it running (Windows)**

Use Task Scheduler pointing at `daemon\run_silent.bat` with trigger "At log on".

### Google Sheet layout

| Column | Content |
|--------|---------|
| `qr_col` (default A) | QR code value / ID |
| `print_col` (default B) | Checkbox — tick to print |

Checked boxes trigger a print. The box stays checked after printing (change detection prevents reprinting on subsequent polls).

