"""Meet Transcript launcher: starts backend on port 8234, shows status window."""
import json
import os
import stat
import subprocess
import sys
import threading
import time
import urllib.request

PORT = 8234
API_URL = f"http://127.0.0.1:{PORT}"

if getattr(sys, "frozen", False):
    _LAUNCHER_DIR = os.path.dirname(sys.executable)
    _MEIPASS = getattr(sys, "_MEIPASS", _LAUNCHER_DIR)
    _APP_DIR = _LAUNCHER_DIR
    if sys.platform == "darwin" and "/Contents/MacOS" in _LAUNCHER_DIR:
        _APP_DIR = _LAUNCHER_DIR.split("/Contents/MacOS")[0]
    _DATA_DIR = os.path.join(os.path.expanduser("~"), "MeetTranscript")
else:
    _LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
    _MEIPASS = _LAUNCHER_DIR
    _APP_DIR = _LAUNCHER_DIR
    _DATA_DIR = _LAUNCHER_DIR

os.makedirs(_DATA_DIR, exist_ok=True)
PROJECT_ROOT = _APP_DIR


def load_dotenv(dirpath):
    """Parse .env file into dict. Skips comments and empty lines."""
    env_path = os.path.join(dirpath, ".env")
    if not os.path.isfile(env_path):
        return {}
    result = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def find_dotenv():
    """Find .env file in known locations, return (dict, path) or ({}, None)."""
    search_dirs = []
    seen = set()
    for d in [_MEIPASS, _LAUNCHER_DIR, _DATA_DIR, _APP_DIR]:
        real = os.path.realpath(d)
        if real not in seen:
            seen.add(real)
            search_dirs.append(d)
    for d in search_dirs:
        dotenv = load_dotenv(d)
        if dotenv:
            return dotenv, os.path.join(d, ".env")
    return {}, None


def build_env():
    """Build environment for backend subprocess: system env + .env file vars."""
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    if getattr(sys, "frozen", False):
        env["APP_MODE"] = "1"
    dotenv, _ = find_dotenv()
    for k, v in dotenv.items():
        if k not in env or not env[k]:
            env[k] = v
    return env


def find_backend_exe():
    """Find bundled backend binary (frozen mode only)."""
    if not getattr(sys, "frozen", False):
        return None
    name = "meet-transcript-backend.exe" if sys.platform == "win32" else "meet-transcript-backend"
    for d in [_MEIPASS, _LAUNCHER_DIR]:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            if sys.platform != "win32":
                try:
                    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                except OSError:
                    pass
            return p
    return None


def _get_log_path():
    return os.path.join(_DATA_DIR, "backend.log")


def start_backend():
    """Start backend process. Returns (Popen, stderr_lines_list) or (None, [reason])."""
    env = build_env()
    stderr_lines = []

    exe = find_backend_exe()
    if exe:
        try:
            p = subprocess.Popen(
                [exe], env=env, cwd=_DATA_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            _start_stderr_reader(p, stderr_lines)
            return p, stderr_lines
        except Exception as e:
            return None, [f"Failed to run backend exe: {e}"]

    main_py = os.path.join(PROJECT_ROOT, "main.py")
    if not os.path.isfile(main_py):
        return None, [f"main.py not found in {PROJECT_ROOT}"]

    try:
        p = subprocess.Popen(
            [sys.executable, main_py], env=env, cwd=_DATA_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        _start_stderr_reader(p, stderr_lines)
        return p, stderr_lines
    except Exception as e:
        return None, [f"Failed to start: {e}"]


def _start_stderr_reader(proc, lines_list):
    """Read combined stdout+stderr, keep last 200 lines in memory and write to log file."""
    log_path = _get_log_path()

    def _reader():
        try:
            with open(log_path, "a", encoding="utf-8", buffering=1) as log_file:
                log_file.write(f"\n=== backend started ===\n")
                for raw in proc.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip()
                    if line:
                        log_file.write(line + "\n")
                        lines_list.append(line)
                        if len(lines_list) > 200:
                            lines_list.pop(0)
        except Exception:
            pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()


def health_ok():
    try:
        with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def get_recording_status():
    try:
        with urllib.request.urlopen(f"{API_URL}/status", timeout=3) as r:
            if r.status == 200:
                return json.loads(r.read().decode())
    except Exception:
        pass
    return {"recording": False}


def run_tk():
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("Meet Transcript")
    root.geometry("380x200")
    root.resizable(False, False)

    label = tk.Label(root, text="Starting backend...", font=tkfont.Font(size=16))
    label.pack(pady=(20, 5))

    detail = tk.Label(root, text="", font=tkfont.Font(size=10), fg="gray", wraplength=340, justify="center")
    detail.pack(pady=(0, 5))

    process_ref = [None]
    stderr_ref = [[]]
    timeout_sec = 90 if getattr(sys, "frozen", False) else 30
    deadline = [0.0]

    def kill_process():
        p = process_ref[0]
        if p is None:
            return
        process_ref[0] = None
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    def do_start():
        kill_process()
        _, env_path = find_dotenv()
        if not env_path:
            expected = os.path.join(_DATA_DIR, ".env")
            label.config(text=".env not found", fg="red")
            detail.config(text=f"Place .env file here:\n{expected}")
            btn_restart.pack(side="left", padx=10)
            return False
        p, stderr_lines = start_backend()
        process_ref[0] = p
        stderr_ref[0] = stderr_lines
        if p is None:
            msg = stderr_lines[0] if stderr_lines else "Unknown error"
            label.config(text="Backend failed to start", fg="red")
            detail.config(text=msg)
            btn_restart.pack(side="left", padx=10)
            return False
        deadline[0] = time.monotonic() + timeout_sec
        return True

    def check_ready():
        p = process_ref[0]
        if p is None:
            return

        rc = p.poll()
        if rc is not None:
            last_err = "\n".join(stderr_ref[0][-5:]) if stderr_ref[0] else f"exit code {rc}"
            label.config(text="Backend crashed", fg="red")
            detail.config(text=last_err)
            process_ref[0] = None
            btn_close.pack_forget()
            btn_restart.pack(side="left", padx=10)
            btn_close.pack(side="left", padx=10)
            return

        if time.monotonic() > deadline[0]:
            kill_process()
            last_err = "\n".join(stderr_ref[0][-3:]) if stderr_ref[0] else "No response on port 8234"
            label.config(text="Backend timed out", fg="red")
            detail.config(text=last_err)
            btn_close.pack_forget()
            btn_restart.pack(side="left", padx=10)
            btn_close.pack(side="left", padx=10)
            return

        if health_ok():
            label.config(text="Not recording", fg="gray")
            detail.config(text=f"Backend ready on port {PORT}")
            btn_restart.pack_forget()
            btn_close.pack(side="left", padx=10)
            root.after(2000, poll_status)
            return

        root.after(400, check_ready)

    def poll_status():
        if process_ref[0] is None:
            return
        rc = process_ref[0].poll()
        if rc is not None:
            label.config(text="Backend stopped", fg="red")
            detail.config(text="Process exited unexpectedly")
            btn_restart.pack(side="left", padx=10)
            return
        try:
            s = get_recording_status()
            if s.get("recording"):
                label.config(text="Recording", fg="green")
            else:
                label.config(text="Not recording", fg="gray")
        except Exception:
            label.config(text="Not recording", fg="gray")
        root.after(2000, poll_status)

    def on_restart():
        for w in btn_frame.winfo_children():
            w.pack_forget()
        label.config(text="Starting backend...", fg="gray")
        detail.config(text="")
        if do_start():
            btn_close.pack(side="left", padx=10)
            root.after(400, check_ready)
        else:
            btn_restart.pack(side="left", padx=10)
            btn_close.pack(side="left", padx=10)

    def on_close():
        kill_process()
        root.destroy()

    log_win_ref = [None]

    def on_show_logs():
        # If window already open — just bring it to front
        if log_win_ref[0] and log_win_ref[0].winfo_exists():
            log_win_ref[0].lift()
            refresh_logs()
            return

        win = tk.Toplevel(root)
        win.title("Logs — Meet Transcript")
        win.geometry("760x500")
        win.resizable(True, True)
        log_win_ref[0] = win

        text_frame = tk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        log_text = tk.Text(
            text_frame,
            font=("Menlo", 10),
            bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white",
            wrap="none",
            yscrollcommand=scrollbar.set,
        )
        log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=log_text.yview)

        # Horizontal scrollbar
        h_scroll = tk.Scrollbar(win, orient="horizontal", command=log_text.xview)
        h_scroll.pack(fill="x", padx=8)
        log_text.config(xscrollcommand=h_scroll.set)

        btn_bar = tk.Frame(win)
        btn_bar.pack(fill="x", padx=8, pady=6)

        auto_scroll = [True]
        shown_lines = [0]   # how many lines we've already inserted into log_text
        all_lines = []      # full list of lines read so far

        def _load_lines():
            """Read lines from log file (preferred) or in-memory buffer."""
            log_path = _get_log_path()
            if os.path.isfile(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        return f.read().splitlines()
                except Exception:
                    pass
            return list(stderr_ref[0])

        def do_refresh():
            nonlocal all_lines
            new_all = _load_lines()
            new_count = len(new_all)
            if new_count <= shown_lines[0]:
                return  # nothing new

            # Append only the new lines — never touch existing text
            new_chunk = new_all[shown_lines[0]:]
            log_text.config(state="normal")
            if shown_lines[0] > 0:
                log_text.insert("end", "\n" + "\n".join(new_chunk))
            else:
                log_text.insert("end", "\n".join(new_chunk))
            log_text.config(state="disabled")

            all_lines = new_all
            shown_lines[0] = new_count

            if auto_scroll[0]:
                log_text.see("end")

        def refresh_logs():
            do_refresh()
            if log_win_ref[0] and log_win_ref[0].winfo_exists():
                win.after(1000, refresh_logs)

        def toggle_scroll():
            auto_scroll[0] = not auto_scroll[0]
            btn_scroll.config(text="Auto-scroll: ON" if auto_scroll[0] else "Auto-scroll: OFF")
            if auto_scroll[0]:
                log_text.see("end")

        def copy_all():
            text = log_text.get("1.0", "end-1c")
            win.clipboard_clear()
            win.clipboard_append(text)
            btn_copy.config(text="Copied!")
            win.after(1500, lambda: btn_copy.config(text="Copy All"))

        def clear_logs():
            log_path = _get_log_path()
            try:
                if os.path.isfile(log_path):
                    open(log_path, "w").close()
            except Exception:
                pass
            stderr_ref[0].clear()
            all_lines.clear()
            shown_lines[0] = 0
            log_text.config(state="normal")
            log_text.delete("1.0", "end")
            log_text.config(state="disabled")

        tk.Button(btn_bar, text="Refresh", command=do_refresh).pack(side="left", padx=4)
        btn_scroll = tk.Button(btn_bar, text="Auto-scroll: ON", command=toggle_scroll)
        btn_scroll.pack(side="left", padx=4)
        btn_copy = tk.Button(btn_bar, text="Copy All", command=copy_all)
        btn_copy.pack(side="left", padx=4)
        tk.Button(btn_bar, text="Clear", command=clear_logs, fg="gray").pack(side="left", padx=4)
        tk.Button(btn_bar, text="Close", command=win.destroy).pack(side="right", padx=4)

        refresh_logs()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=(5, 15))
    btn_restart = tk.Button(btn_frame, text="Restart", command=on_restart)
    btn_close = tk.Button(btn_frame, text="Close", command=on_close)
    btn_logs = tk.Button(btn_frame, text="Logs", command=on_show_logs, fg="gray")

    btn_logs.pack(side="left", padx=10)
    if do_start():
        btn_close.pack(side="left", padx=10)
        root.after(400, check_ready)
    else:
        btn_restart.pack(side="left", padx=10)
        btn_close.pack(side="left", padx=10)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    run_tk()
