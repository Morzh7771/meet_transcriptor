"""
Pack Chrome extension into zip for distribution.
Run from project root: uv run python scripts/pack_extension.py
Output: dist/Meet-Transcript-Extension.zip
"""
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = PROJECT_ROOT / "extension"
DIST = PROJECT_ROOT / "dist"
OUT_ZIP = DIST / "Meet-Transcript-Extension.zip"


def main():
    DIST.mkdir(exist_ok=True)
    prefix = "Meet-Transcript-Extension"
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in EXT_DIR.iterdir():
            if f.name.startswith(".") or f.name == "node_modules":
                continue
            if f.is_file():
                zf.write(f, f"{prefix}/{f.name}")
            elif f.is_dir():
                for sub in f.rglob("*"):
                    if sub.is_file():
                        zf.write(sub, f"{prefix}/{sub.relative_to(EXT_DIR)}")
    print(f"Done: {OUT_ZIP}")
    print("Install: unzip -> Chrome -> Extensions -> Developer mode -> Load unpacked -> select folder.")


if __name__ == "__main__":
    main()
