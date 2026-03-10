# Build: 2 files for distribution

Result: **1) app** (backend + status window), **2) extension** (Chrome zip).

Backend and extension communicate on **port 8234**.

---

## 1. App (backend + window)

Runs API on `http://127.0.0.1:8234`, shows window with recording status.

### Development (no build)

```bash
uv run python launcher.py
```

Requires dependencies (`uv sync`) and port 8234 free.

### Build into single file

```bash
uv add --dev pyinstaller
uv run python scripts/build_app.py
```

- **Windows:** `dist/Meet Transcript.exe`
- **Mac:** `dist/Meet Transcript`

**IMPORTANT:** copy `.env` file next to the built app before running it.

---

## 2. Chrome Extension

### Pack into zip

```bash
uv run python scripts/pack_extension.py
```

Result: **`dist/Meet-Transcript-Extension.zip`**

### Install

1. Unzip `Meet-Transcript-Extension.zip`.
2. Chrome -> `chrome://extensions` -> enable **Developer mode**.
3. **Load unpacked** -> select the unzipped folder (must contain `manifest.json`).

---

## User flow

1. Place `.env` next to the app (with GROQ_API_KEY, AWS keys etc).
2. Run the app. Window shows "Not recording" = backend is ready on 8234.
3. Install extension from zip.
4. Join Google Meet, click Start in extension -> window shows "Recording".
