import asyncio
import subprocess

NODE_SCRIPT_PATH = "js/meet_stream.js"

async def run_node_script(email, password, meet_code, duration_sec):
    command = [
        "node", NODE_SCRIPT_PATH,
        email, password, meet_code, str(duration_sec)
    ]
    print("▶️ Launche Node.js:", " ".join(command))
    await asyncio.to_thread(subprocess.run, command)
    print("✅ Node.js End.")