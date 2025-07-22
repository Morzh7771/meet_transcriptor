import asyncio
from src.backend.core.facade import Facade

BACKEND_URL = "http://localhost:3000"
facade = Facade()

async def main():
    await facade.run_google_meet_recording()

if __name__ == "__main__":
    asyncio.run(main())
