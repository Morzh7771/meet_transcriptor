"""
Build backend into a single executable (PyInstaller).
Run from project root: uv run python scripts/build_backend.py
Output: dist/meet-transcript-backend (or .exe on Windows)
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_binary(name: str) -> Path | None:
    """Find a binary by name, checking PATH and common macOS Homebrew locations."""
    found = shutil.which(name)
    if found:
        return Path(found)
    for prefix in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        p = Path(prefix) / name
        if p.exists():
            return p
    return None


def main():
    is_win = platform.system() == "Windows"
    exe_name = "meet-transcript-backend.exe" if is_win else "meet-transcript-backend"
    work_dir = PROJECT_ROOT / "build" / "pyinstaller"
    dist_dir = PROJECT_ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    src = PROJECT_ROOT / "src"
    sep = ";" if is_win else ":"
    add_data = f"{src}{sep}src"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        str(PROJECT_ROOT / "main.py"),
        "--onefile",
        "--name", "meet-transcript-backend",
        f"--add-data={add_data}",
        "--clean",
        "--noconfirm",
        "--workpath", str(work_dir),
        "--specpath", str(PROJECT_ROOT),
        "--distpath", str(dist_dir),
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.lifespan.off",
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--collect-all", "groq",
        "--collect-all", "pydub",
        "--hidden-import=boto3",
        "--hidden-import=botocore",
        "--hidden-import=s3transfer",
        "--collect-data=botocore",
        "--hidden-import=requests",
        "--collect-submodules", "src.backend",
    ]

    # Bundle ffmpeg and ffprobe so pydub works without system install
    for binary in ["ffmpeg", "ffprobe"]:
        path = find_binary(binary)
        if path:
            cmd += ["--add-binary", f"{path}:."]
            print(f"Bundling {binary}: {path}")
        else:
            print(f"WARNING: {binary} not found — audio preprocessing will fail in the built app.")
            print(f"  Install via: brew install ffmpeg")

    print("Running PyInstaller for backend...")
    r = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if r.returncode != 0:
        sys.exit(r.returncode)

    dist_exe = dist_dir / exe_name
    if not dist_exe.exists():
        print(f"Build failed: {dist_exe} not found")
        sys.exit(1)

    print(f"Backend built: {dist_exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
