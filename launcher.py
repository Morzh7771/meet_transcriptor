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


# ---------------------------------------------------------------------------
# File transcription helpers
# ---------------------------------------------------------------------------

def _find_ffmpeg():
    """Return path to ffmpeg executable or None if not found."""
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _extract_audio(video_path, output_mp3, log_fn):
    """Extract audio track from video to mp3 using ffmpeg. Returns True on success."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        log_fn("ffmpeg not found. Install it: brew install ffmpeg")
        return False
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-q:a", "4",
        "-ar", "16000", "-ac", "1",
        output_mp3,
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        if r.returncode != 0:
            log_fn("ffmpeg error:\n" + r.stdout.decode("utf-8", errors="replace")[-800:])
            return False
        return True
    except subprocess.TimeoutExpired:
        log_fn("ffmpeg timed out (>15 min)")
        return False
    except Exception as e:
        log_fn(f"ffmpeg failed: {e}")
        return False


def _split_audio_chunks(audio_path, tmp_files, log_fn, chunk_secs=600):
    """Split audio into chunks of chunk_secs seconds. Returns list of paths or []."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        log_fn("ffmpeg not found — cannot split large audio")
        return []
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="transcript_chunks_")
    tmp_files.append(tmp_dir)
    pattern = os.path.join(tmp_dir, "chunk_%03d.mp3")
    cmd = [
        ffmpeg, "-y", "-i", audio_path,
        "-f", "segment", "-segment_time", str(chunk_secs),
        "-acodec", "libmp3lame", "-q:a", "4",
        pattern,
    ]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
        if r.returncode != 0:
            log_fn("ffmpeg split error:\n" + r.stdout.decode("utf-8", errors="replace")[-500:])
            return []
    except Exception as e:
        log_fn(f"ffmpeg split failed: {e}")
        return []
    chunks = sorted(
        os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.endswith(".mp3")
    )
    log_fn(f"Split into {len(chunks)} chunks of ~{chunk_secs//60} min each")
    return chunks


def _groq_whisper_upload(audio_path, api_key, model):
    """POST audio file to Groq Whisper API. Returns transcript text or raises."""
    import requests

    filename = os.path.basename(audio_path)
    with open(audio_path, "rb") as f:
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, f, "audio/mpeg")},
            data={"model": model, "response_format": "text"},
            timeout=300,
        )
    if not resp.ok:
        raise RuntimeError(f"{resp.status_code} {resp.reason}: {resp.text[:300]}")
    return resp.text


def open_transcript_window(parent):
    """Open the file transcription window."""
    import tkinter as tk
    from tkinter import filedialog, font as tkfont
    import tempfile

    _ALL_AV = (
        "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.opus *.wma *.aiff *.aif *.amr *.ra *.caf "
        "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.m4v *.webm *.ts *.mts *.m2ts *.3gp *.3g2 "
        "*.ogv *.vob *.rm *.rmvb *.divx *.f4v *.asf"
    )

    win = tk.Toplevel(parent)
    win.title("File Transcription")
    win.geometry("580x460")
    win.resizable(True, True)

    pad = {"padx": 12, "pady": 4}

    # --- Input file row ---
    tk.Label(win, text="Input file (audio or video):", anchor="w").pack(fill="x", **pad)
    row1 = tk.Frame(win)
    row1.pack(fill="x", padx=12, pady=2)
    input_var = tk.StringVar()
    tk.Entry(row1, textvariable=input_var, font=tkfont.Font(size=10)).pack(side="left", fill="x", expand=True)

    def browse_input():
        path = filedialog.askopenfilename(
            parent=win,
            title="Select audio or video file",
            filetypes=[
                ("Audio / Video (all formats)", _ALL_AV),
                ("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.opus *.wma *.aiff *.aif *.amr *.ra *.caf *.webm"),
                ("Video", "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.m4v *.webm *.ts *.mts *.3gp *.ogv *.vob *.rm *.rmvb"),
                ("All files", "*.*"),
            ],
        )
        if path:
            input_var.set(path)

    tk.Button(row1, text="Browse…", command=browse_input).pack(side="left", padx=(6, 0))

    # --- Output folder row ---
    tk.Label(win, text="Save transcript to folder:", anchor="w").pack(fill="x", **pad)
    row2 = tk.Frame(win)
    row2.pack(fill="x", padx=12, pady=2)
    output_var = tk.StringVar()
    tk.Entry(row2, textvariable=output_var, font=tkfont.Font(size=10)).pack(side="left", fill="x", expand=True)

    def browse_output():
        path = filedialog.askdirectory(parent=win, title="Select output folder")
        if path:
            output_var.set(path)

    tk.Button(row2, text="Browse…", command=browse_output).pack(side="left", padx=(6, 0))

    # --- Status label ---
    status_lbl = tk.Label(win, text="Ready", fg="gray", font=tkfont.Font(size=10))
    status_lbl.pack(anchor="w", **pad)

    # --- Log text area ---
    log_frame = tk.Frame(win)
    log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
    sb = tk.Scrollbar(log_frame)
    sb.pack(side="right", fill="y")
    log_text = tk.Text(
        log_frame, height=10,
        font=("Menlo", 9),
        bg="#1e1e1e", fg="#d4d4d4",
        insertbackground="white",
        wrap="word",
        yscrollcommand=sb.set,
        state="disabled",
    )
    log_text.pack(side="left", fill="both", expand=True)
    sb.config(command=log_text.yview)

    # --- Start button ---
    start_btn = tk.Button(win, text="Start Transcription", font=tkfont.Font(size=12, weight="bold"))
    start_btn.pack(pady=(4, 10))

    # --- Helpers ---
    def _log(msg):
        def _do():
            log_text.config(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.config(state="disabled")
        win.after(0, _do)

    def _set_status(msg, color="gray"):
        win.after(0, lambda: status_lbl.config(text=msg, fg=color))

    def _clear_log():
        log_text.config(state="normal")
        log_text.delete("1.0", "end")
        log_text.config(state="disabled")

    # --- Transcription worker ---
    def do_transcribe():
        input_path = input_var.get().strip()
        output_dir = output_var.get().strip()

        if not input_path:
            _set_status("Select input file", "red")
            return
        if not os.path.isfile(input_path):
            _set_status("Input file not found", "red")
            return
        if not output_dir:
            _set_status("Select output folder", "red")
            return
        if not os.path.isdir(output_dir):
            _set_status("Output folder not found", "red")
            return

        dotenv, _ = find_dotenv()
        api_key = dotenv.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            _set_status("GROQ_API_KEY not set in .env", "red")
            return
        model = dotenv.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

        start_btn.config(state="disabled")
        _clear_log()
        _set_status("Working…", "orange")

        def run():
            tmp_files = []
            try:
                # Step 1 — always convert through ffmpeg (handles every format uniformly).
                # If ffmpeg is missing, fall back to uploading the original file directly.
                if _find_ffmpeg():
                    _log("Converting to audio via ffmpeg…")
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tmp.close()
                    tmp_files.append(tmp.name)
                    if not _extract_audio(input_path, tmp.name, _log):
                        _set_status("Audio extraction failed", "red")
                        return
                    audio_path = tmp.name
                    _log("Audio ready.\n")
                else:
                    _log("ffmpeg not found — uploading original file directly.\n"
                         "(Install ffmpeg for full format support: brew install ffmpeg)\n")
                    audio_path = input_path

                # Step 2 — check file size, split if > 24 MB
                size_mb = os.path.getsize(audio_path) / (1024 * 1024)
                _log(f"Audio size: {size_mb:.1f} MB")

                if size_mb > 24:
                    _log("File too large for direct upload — splitting into 10-min chunks…")
                    chunks = _split_audio_chunks(audio_path, tmp_files, _log)
                    if not chunks:
                        _set_status("Failed to split audio", "red")
                        return
                else:
                    chunks = [audio_path]

                # Step 3 — transcribe each chunk
                parts = []
                for i, chunk in enumerate(chunks, 1):
                    label = f"part {i}/{len(chunks)}" if len(chunks) > 1 else "file"
                    _log(f"Transcribing {label} with Groq ({model})…")
                    try:
                        text = _groq_whisper_upload(chunk, api_key, model)
                        parts.append(text.strip())
                        _log(f"  Done ({label}).")
                    except Exception as e:
                        _log(f"Groq error: {e}")
                        _set_status("Transcription failed", "red")
                        return

                full_text = "\n\n".join(parts)

                # Step 4 — save
                base = os.path.splitext(os.path.basename(input_path))[0]
                out_path = os.path.join(output_dir, base + "_transcript.txt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(full_text)

                _log(f"\nTranscript saved to:\n{out_path}")
                _set_status("Done!", "green")

            except Exception as e:
                _log(f"Unexpected error: {e}")
                _set_status("Error", "red")
            finally:
                for tmp in tmp_files:
                    try:
                        if os.path.isdir(tmp):
                            import shutil
                            shutil.rmtree(tmp, ignore_errors=True)
                        elif os.path.isfile(tmp):
                            os.unlink(tmp)
                    except Exception:
                        pass
                win.after(0, lambda: start_btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    start_btn.config(command=do_transcribe)


def run_tk():
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("Meet Transcript")
    root.geometry("460x200")
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
    btn_transcript = tk.Button(
        btn_frame, text="Transcript",
        command=lambda: open_transcript_window(root),
        fg="#2d6cdf",
    )

    btn_logs.pack(side="left", padx=10)
    btn_transcript.pack(side="left", padx=10)
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
