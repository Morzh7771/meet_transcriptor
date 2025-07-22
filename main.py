import asyncio
from src.backend.core.facade import Facade

facade = Facade()

async def main():
    await facade.run_google_meet_recording()

if __name__ == "__main__":
    asyncio.run(main())
