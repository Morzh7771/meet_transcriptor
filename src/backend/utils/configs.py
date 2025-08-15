import json
from pathlib import Path
from typing import Any, Dict
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.backend import db


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class OpenAIConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    API_KEY: SecretStr = Field(
        ..., description="The API key for the OpenAI service"
    )













class Config(BaseSettings):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)


    @classmethod
    def load_config(cls) -> "Config":
        return cls()



