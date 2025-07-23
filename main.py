import asyncio
import subprocess
import re
import socket
import random
from src.backend.core.facade import Facade

facade = Facade()

async def main():
    await facade.run_google_meet_recording()



    raise RuntimeError("Не удалось найти свободный порт.")
async def pivo():
    free_port = await find_free_port()
    print(f"✅ Свободный порт найден: {free_port}")

if __name__ == "__main__":
    #asyncio.run(main())
    asyncio.run(pivo())
