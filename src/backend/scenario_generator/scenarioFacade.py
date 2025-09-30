import asyncio
import os
from typing import Optional, List
from openai import OpenAI

from src.backend.scenario_generator.datascrapper import ClientDataReader, FullClientData
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.utils.configs import Config

class ScenarioFacade:
    def __init__(self):
        self.configs = Config().load_config()
        self.client_reader = ClientDataReader()
        self.prompt_facade = PromptFacade()
        self.client = OpenAI(api_key=self.configs.openai.API_KEY.get_secret_value())

    def get_prompt_with_context(self, template_name: str, current_user: FullClientData, similar_users: list) -> str:
        try:
            template_vars = {
                "current_user": current_user.to_dict() if current_user else {},
                "similar_users": [u.to_dict() for u in similar_users] if similar_users else [],
                "user_count": len(similar_users) if similar_users else 0,
            }
            return self.prompt_facade.get_prompt(template_name, **template_vars)
        except Exception as e:
            raise Exception(f"Error generating prompt using PromptFacade: {str(e)}")

    async def call_llm(self, prompt: str) -> str:
        """Use OpenAI 1.x client; wrap sync call in a worker thread for asyncio compatibility."""
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1")
        def _call():
            return self.client.chat.completions.create(
                model=chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at creating personalized scenarios for customers based on their data "
                            "and similar customers. Provide detailed, actionable scenarios that can help insurance "
                            "consultants better understand and serve their clients."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2500,
            )
        response = await asyncio.to_thread(_call)
        return response.choices[0].message.content.strip()

    async def generate_scenario_for_user(self, user_email: str, template_name: str = "scenario", similar_count: int = 3) -> str:
        try:
            print(f"Generating scenario for user: {user_email}")
            current_user = await self.client_reader.get_client_by_email(user_email)
            if not current_user:
                raise Exception(f"User with email {user_email} is not found.")
            print(f"User founded: {current_user.person.first_name} {current_user.person.last_name}")

            similar_data = await self.client_reader.get_similar_clients_for_target(user_email, similar_count, update_vector_db=True)
            if isinstance(similar_data, dict) and "error" in similar_data:
                print(f"ALARM: {similar_data['error']}")
                similar_users: List[FullClientData] = []
            else:
                similar_users = [item["client_data"] for item in similar_data.get("similar_clients", [])]
                print(f"Founded {len(similar_users)} similar users")
            print(similar_users)
            print(f"Generating prompt with template: {template_name}")
            prompt = self.get_prompt_with_context(template_name, current_user, similar_users)

            print("Sending a request to LLM...")
            scenario = await self.call_llm(prompt)
            print("The script was generated successfully.")
            return scenario
        except Exception as e:
            print(f"Error generating script: {str(e)}")
            raise

    

# async def generate_scenario_for_email(user_email: str, template_name: str = "scenario") -> str:
#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         raise Exception("The environment variable is not set. OPENAI_API_KEY")
#     generator = ScenarioGenerator(api_key)
#     return await generator.generate_scenario_for_user(user_email, template_name)

 