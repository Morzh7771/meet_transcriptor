import asyncio
from src.backend.modules.chatBot import ChatBot
import time


async def main():
    # chat_bot = ChatBot()
    # answer = await chat_bot.process_message("38a6f98d-21cb-4f1e-8060-ae2455a0e063", 1755365529, "user", "What Alice said about the new meeting", ["Bob: When will be our next meeting and what it will be about?", "Clare: I think, it will be on Monday at 1 pm", "Alice: No, I think it will be on Tuesday at 1 pm"])
    time1 = time.time()
    print(f"The answer is: {time1}")


if __name__ == "__main__":
    asyncio.run(main())
