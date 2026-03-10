"""
Build full app: backend exe + launcher with window, bundled into one file.
Run from project root: uv run python scripts/build_app.py
Output: dist/Meet Transcript (Mac) or dist/Meet Transcript.exe (Windows)
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST = PROJECT_ROOT / "dist"
BACKEND_EXE = "meet-transcript-backend.exe" if platform.system() == "Windows" else "meet-transcript-backend"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd or str(PROJECT_ROOT))
    if r.returncode != 0:
        sys.exit(r.returncode)


def main():
    DIST.mkdir(exist_ok=True)
    backend_path = DIST / BACKEND_EXE
    if not backend_path.exists():
        print("Building backend first...")
        run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_backend.py")])
    if not backend_path.exists():
        print(f"Error: backend not built at {backend_path}")
        sys.exit(1)

    print("Building launcher...")
    sep = ";" if platform.system() == "Windows" else ":"
    add_binary = f"{backend_path}{sep}."
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "Meet Transcript",
        "--windowed",
        f"--add-binary={add_binary}",
        "--clean", "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(PROJECT_ROOT / "build" / "launcher"),
        "--specpath", str(PROJECT_ROOT),
        str(PROJECT_ROOT / "launcher.py"),
    ]
    run(cmd)

    exe_name = "Meet Transcript.exe" if platform.system() == "Windows" else "Meet Transcript"
    app_path = DIST / exe_name
    if not app_path.exists():
        print("Error: launcher build failed")
        sys.exit(1)

    env_src = PROJECT_ROOT / ".env"
    if env_src.exists():
        env_dst = DIST / ".env"
        shutil.copy2(env_src, env_dst)
        print(f"Copied .env to {env_dst}")
        if sys.platform == "darwin":
            app_bundle = DIST / "Meet Transcript.app"
            macos_dir = app_bundle / "Contents" / "MacOS"
            if macos_dir.is_dir():
                bundle_env = macos_dir / ".env"
                shutil.copy2(env_src, bundle_env)
                print(f"Copied .env into bundle: {bundle_env}")
        data_dir = Path.home() / "MeetTranscript"
        data_dir.mkdir(exist_ok=True)
        data_env = data_dir / ".env"
        if not data_env.exists():
            shutil.copy2(env_src, data_env)
            print(f"Copied .env to {data_env}")
    else:
        data_dir = Path.home() / "MeetTranscript"
        print(f"WARNING: no .env found. Place .env in {data_dir}/ before running the app.")

    print(f"Done: {app_path}")


if __name__ == "__main__":
    main()
