import asyncio
from typing import Optional, List
from pydantic import BaseModel

from src.backend.scenario_generator.datascrapper import ClientDataReader, FullClientData
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.utils.configs import Config
from src.backend.core.baseFacade import BaseFacade
from src.backend.utils.logger import CustomLog


class ValidationResult(BaseModel):
    is_valid: bool
    feedback: str


class ScenarioFacade(BaseFacade):
    def __init__(self):
        super().__init__()
        self.client_reader = ClientDataReader()
        self.prompt_facade = PromptFacade()
        self.chat_model = "gpt-4.1"

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

    async def call_llm_for_scenario(self, prompt: str) -> str:
        """Используем BaseFacade.completion для вызова LLM"""
        try:
            # Получаем шаблон промпта (должен быть список словарей с 'role' и 'content')
            llm_scenario_template_str = self.prompt_facade.get_prompt("llm_scenario_template", prompt=prompt)
            
            # Безопасный eval или лучше использовать json.loads если это JSON
            messages = eval(llm_scenario_template_str)
            
            # Проверяем структуру messages
            if not isinstance(messages, list):
                raise ValueError("llm_scenario_template должен возвращать список сообщений")
            
            # Вызываем через BaseFacade.completion
            response = await self.completion(
                model=self.chat_model,
                messages=messages,
                temperature=0.3,
                max_tokens=2500,
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error calling LLM for scenario: {str(e)}")
            raise

    async def generate_scenario_for_user(self, client_email: str, template_name: str = "scenario", similar_count: int = 3) -> str:
        try:
            self.logger.info(f"Generating scenario for user: {client_email}")
            current_client = await self.client_reader.get_client_by_email(client_email)
            if not current_client:
                raise Exception(f"User with email {client_email} is not found.")
            self.logger.info(f"User founded: {current_client.person.first_name} {current_client.person.last_name}")

            similar_data = await self.client_reader.get_similar_clients_for_target(client_email, similar_count, update_vector_db=True)
            if isinstance(similar_data, dict) and "error" in similar_data:
                self.logger.error(f"ALARM: {similar_data['error']}")
                similar_clients: List[FullClientData] = []
            else:
                similar_clients = [item["client_data"] for item in similar_data.get("similar_clients", [])]
                self.logger.info(f"Founded {len(similar_clients)} similar users")
            
            self.logger.info(similar_clients)
            self.logger.info(f"Generating prompt with template: {template_name}")
            prompt = self.get_prompt_with_context(template_name, current_client, similar_clients)

            self.logger.info("Sending a request to LLM...")
            scenario = await self.call_llm_for_scenario(prompt)
            self.logger.info("The script was generated successfully.")
            return scenario
        except Exception as e:
            self.logger.error(f"Error generating script: {str(e)}")
            raise

    # --------------------------VALIDATION--------------------------

    async def validate_chunk_against_scenario(self, scenario: str, chunk_text: str) -> str:
        try:
            # Получаем шаблон промпта
            validate_scenario_template_str = self.prompt_facade.get_prompt(
                "validate_scenario_template",
                scenario=scenario,
                chunk_text=chunk_text
            )
            
            messages = eval(validate_scenario_template_str)
         
            # Вызываем через BaseFacade.completion
            response = await self.completion(
                model=self.chat_model,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error validating chunk: {str(e)}")
            raise