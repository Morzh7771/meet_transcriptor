import asyncio
from src.backend.core.facade import Facade

facade = Facade()

async def command_listener():
    while True:
        try:
            command = await asyncio.to_thread(input, ">>> ")

            if command.startswith("terminate "):
                _, meet_code = command.split(" ", 1)
                meet_code = meet_code.strip()
                if meet_code:
                    await facade.js_plugin_api.terminate_by_meet_code(meet_code)
                else:
                    print("⚠️  Meet code is missing in the command.")
            else:
                print("❓ Unknown command. Use: terminate <meet_code>")

        except Exception as e:
            print(f"❌ Error reading command: {e}")

async def main():
    await asyncio.gather(
        facade.run_google_meet_recording(),
        command_listener()
    )

if __name__ == "__main__":
    asyncio.run(main())
