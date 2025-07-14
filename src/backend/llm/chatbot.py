from openai import OpenAI
from dotenv import load_dotenv
import os
from src.backend.utils.logger import CustomLog
from src.backend.llm.HistoryFacade import HistoryFacade, HistoryUnit

log = CustomLog()

# load environment variables from .env
load_dotenv()


class ChatBot:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing in .env")
        self.client = OpenAI(api_key=api_key)
        self.history_facade = HistoryFacade()



    def ask(self, question: str, context: str):
        """
        Streamed answer: yields partial chunks of the answer.
        """
        uuid = "55555"
        try:
            log.info(f"Sending question to ChatBot: {question}")

            history = self.history_facade.get_history(uuid)


            try:
                with open("transcript.txt", "r", encoding="utf-8") as f:
                    last_meet = f.read()
            except FileNotFoundError:
                last_meet = ""
            except Exception as e:
                log.warning(f"Error reading transcript file: {e}")
                last_meet = ""

            stream = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": """
                            You are a senior interviewer. We are creating a new startup. And now we have an interview with a potential customer.
                            Our idea - to create a system that will listen all meetings, read info from chats, and in time of new interviewer will be available to answer questions.
                            So, now we are interviewing a potential customer. Right now. And all questions that we ask to you have to be answered in the context of the meeting. 
                            You can suggest to ask more questions if you will see that we not have enough information for our product development. 
                            But your main task - answer our questions and tasks. Like - make summary of the meeting, make a list of questions that we need to ask to the customer, etc.
                            And of course - you will have history of our conversation, and transcripts from previous meetings. Use them too to answer our questions and tasks.

                            Be very careful and accurate in your answers.
                        """
                    },
                    {
                        "role": "user",
                        "content": f"""
                            Our new message to you: {question}
                            Current meeting transcript: {context}
                            History: {history}
                            Previous meeting transcript. Use it only to answer question about previous meeting. Like compare or something like that: {last_meet}
                        """
                    }
                ],
                temperature=0.5,
                stream=True
            )
            response = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    response += delta.content
                    yield delta.content

            self.history_facade.add_user_message(uuid, question)
            self.history_facade.add_bot_message(uuid, response)
        except Exception as e:
            log.error(f"ChatBot streaming error: {e}")
            yield "An error occurred while generating the answer."
