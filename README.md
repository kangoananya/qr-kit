# qr-kit

A pair of lightweight, standalone browser tools for QR codes — no build step, no dependencies to install.

## Tools

| File | Tool | Description |
|------|------|-------------|
| `index.html` | **Scanner** | Opens your device camera and decodes QR codes in real time |
| `generator.html` | **Label Generator** | Create and print QR code labels from a form |

## Usage

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

## Browser Support

| Browser | Scanner | Generator |
|---------|---------|-----------|
| Chrome 90+ / Android | ✅ Native `BarcodeDetector` | ✅ |
| iOS Safari 14.3+ | ✅ jsQR fallback | ✅ |
| Firefox | ✅ jsQR fallback | ✅ |
| Samsung Internet | ✅ jsQR fallback | ✅ |
