import asyncio
from src.backend.modules.transcriber import Transcriber
from src.backend.modules.chatBot import ChatBot
# import sys
# import os


async def main():
    chat_bot = ChatBot()
    answer = await chat_bot.process_message("What is the capital of Ukraine?")
    print(f"The answer is: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
