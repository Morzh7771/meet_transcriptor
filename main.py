import asyncio
import websockets
import json
import os
import time
import aiohttp

# === Settings ===
BACKEND_URL = "http://localhost:3000"
timestamp = time.strftime("%Y-%m-%d_%H-%M")
OUTPUT_FILE = f"recordings/meet_audio_{timestamp}.webm"

# === Data ===
email = "quantexttestmeeat@gmail.com"
password = "Quantextisthebest"
phone = "+380956069731"
meet_code = "jsa-vatt-ovo"
duration_sec = 30

# === Functions ===

async def login():
    async with aiohttp.ClientSession() as session:
        print("🔐 Sending request to /start-login...")
        response = await session.post(
            f"{BACKEND_URL}/start-login",
            json={"email": email, "password": password, "phone": phone}
        )
        text = await response.text()
        print(f"📨 Server response: {response.status} — {text}")
        submit_2fa()

async def submit_2fa():
    code = input("Enter the 2FA code and press Enter: ")
    async with aiohttp.ClientSession() as session:
        print("🔐 Sending code to /submit-2fa...")
        response = await session.post(
            f"{BACKEND_URL}/submit-2fa",
            json={"code": code}
        )
        text = await response.text()
        print(f"📨 Server response: {response.status} — {text}")

async def connect(code = "kow-xrgf-nty", port = 8765):
    os.makedirs("recordings", exist_ok=True)
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    print("🟢 Starting WebSocket server...")

    connection_closed = asyncio.Event()

    async def handler(websocket):
        print("🔌 Connection received. Recording and tracking started...")
        with open(OUTPUT_FILE, "wb") as f:
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        f.write(message)
                        print(f"🎙️ Audio chunk received: {len(message)} bytes")
                    elif isinstance(message, str):
                        try:
                            data = json.loads(message)
                            timestamp = time.strftime('%H:%M:%S', time.localtime(data.get("time", time.time())))
                            speakers = data.get("speakers", {})
                            print(f"🗣️ {timestamp} | Speaking: " +
                                  ", ".join(f"{k}: {'🎤' if v else '—'}" for k, v in speakers.items()))
                        except json.JSONDecodeError:
                            print("⚠️ Invalid JSON message received:", message)
                    else:
                        print("⚠️ Unknown message type")
            except websockets.exceptions.ConnectionClosed:
                print("🔌 WebSocket client disconnected.")
            finally:
                connection_closed.set()

    server = await websockets.serve(handler, "localhost", port)
    print(f"📡 WebSocket listening at ws://localhost:{port}")

    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{BACKEND_URL}/start",
            json={"email": email, "password": password, "meetCode": code, "duration": duration_sec, "port": port}
        )
        text = await response.text()
        print(f"▶️ Start command sent, response: {response.status} — {text}")

    # Wait for WebSocket session to finish
    await connection_closed.wait()

    server.close()
    await server.wait_closed()
    print("✅ Recording finished. File saved:", OUTPUT_FILE)

# === Main entry point ===

async def main():
    print("Choose an action:")
    print("🔹 login   — send email/password")
    print("🔹 connect — start receiving audio stream")

    command = input("👉 Enter a command (login / connect): ").strip().lower()

    if command == "login":
        await login()
    elif command == "connect":
        #code = input("👉 Enter the room code: ").strip().lower()
        #port = input("👉 Enter the WebSocket port: ").strip().lower()
        await connect()
    else:
        print("❌ Unknown command")

if __name__ == "__main__":
    asyncio.run(main())
