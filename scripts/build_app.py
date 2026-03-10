"""
Build full app: backend exe + launcher with window, bundled into one file.
Run from project root: uv run python scripts/build_app.py
Output:
  Mac:     dist/Meet Transcript mac.app  +  dist/Meet Transcript mac.zip
  Windows: dist/Meet Transcript win.exe
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST = PROJECT_ROOT / "dist"
IS_MAC = sys.platform == "darwin"
IS_WIN = platform.system() == "Windows"
BACKEND_EXE = "meet-transcript-backend.exe" if IS_WIN else "meet-transcript-backend"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd or str(PROJECT_ROOT))
    if r.returncode != 0:
        sys.exit(r.returncode)


def bundle_env(env_src: Path, app_bundle: Path):
    """Copy .env into Contents/MacOS/ so the app is self-contained."""
    macos_dir = app_bundle / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    dst = macos_dir / ".env"
    shutil.copy2(env_src, dst)
    print(f"Bundled .env → {dst}")


def sign_app(app_bundle: Path):
    """Ad-hoc code sign so macOS won't mark the app as damaged after unzip."""
    print("Signing app (ad-hoc)...")
    run(["codesign", "--deep", "--force", "--sign", "-", str(app_bundle)])
    print("Signed.")


def make_zip(app_bundle: Path, zip_path: Path):
    """Create a zip with ditto — preserves resource forks and code signature."""
    if zip_path.exists():
        zip_path.unlink()
    print(f"Creating zip with ditto → {zip_path}")
    run([
        "ditto", "-c", "-k", "--sequester-rsrc", "--keepParent",
        str(app_bundle), str(zip_path),
    ])
    print(f"Zip ready: {zip_path}")


def main():
    DIST.mkdir(exist_ok=True)

    backend_path = DIST / BACKEND_EXE
    if not backend_path.exists():
        print("Building backend first...")
        run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_backend.py")])
    if not backend_path.exists():
        print(f"Error: backend not built at {backend_path}")
        sys.exit(1)

    # Choose output name: "Meet Transcript mac" / "Meet Transcript win"
    platform_suffix = "mac" if IS_MAC else "win"
    app_display_name = f"Meet Transcript {platform_suffix}"

    env_src = PROJECT_ROOT / ".env"

    print("Building launcher...")
    sep = ";" if IS_WIN else ":"
    add_binary = f"{backend_path}{sep}."
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", app_display_name,
        "--windowed",
        f"--add-binary={add_binary}",
        "--clean", "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(PROJECT_ROOT / "build" / "launcher"),
        "--specpath", str(PROJECT_ROOT),
    ]
    if IS_WIN and env_src.exists():
        cmd.append(f"--add-data={env_src}{sep}.")
        print("Bundling .env inside exe")
    cmd.append(str(PROJECT_ROOT / "launcher.py"))
    run(cmd)

    if IS_WIN:
        exe_path = DIST / f"{app_display_name}.exe"
        if not exe_path.exists():
            print("Error: launcher build failed")
            sys.exit(1)
        if not env_src.exists():
            print("WARNING: .env not found — app will not work without it!")
        print(f"Done: {exe_path}")
        return

    # ── macOS ──────────────────────────────────────────────────────────────
    app_bundle = DIST / f"{app_display_name}.app"
    if not app_bundle.exists():
        print(f"Error: app bundle not found at {app_bundle}")
        sys.exit(1)

    if not env_src.exists():
        print(f"WARNING: .env not found at {env_src} — app will not work without it!")
    else:
        bundle_env(env_src, app_bundle)

    sign_app(app_bundle)

    zip_path = DIST / f"{app_display_name}.zip"
    make_zip(app_bundle, zip_path)

    print(f"\nDone!")
    print(f"  App bundle : {app_bundle}")
    print(f"  Zip to send: {zip_path}")
    print()
    print("Note: if macOS still shows a warning after unzip, the user should")
    print("  right-click the app → Open → Open (only needed once).")


if __name__ == "__main__":
    main()
