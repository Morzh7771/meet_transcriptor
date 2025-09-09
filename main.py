import asyncio
from src.backend.core.Facade import Facade

facade = Facade()

async def command_listener(facade_: Facade):
    while not facade_.session_done.is_set():
        try:
            command = await asyncio.to_thread(input, ">>> ")

            if command.startswith("terminate "):
                _, meet_code = command.split(" ", 1)
                meet_code = meet_code.strip()
                if meet_code:
                    await facade_.js_plugin_api.terminate_by_meet_code(meet_code)
                else:
                    print("⚠️  Meet code is missing in the command.")
            else:
                print("❓ Unknown command. Use: terminate <meet_code>")

        except Exception as e:
            print(f"❌ Error reading command: {e}")

async def main():
    await asyncio.gather(
        facade.run_google_meet_recording_api("611a7f92-f6ad-4458-9e82-af5cca23575e", "nzz-tevk-zab", "ru"), # Paste the user_id, meet code and meet language here
        command_listener(facade)
    )

if __name__ == "__main__":
    asyncio.run(main())
