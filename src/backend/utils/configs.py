import json
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Dict
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.backend import db

class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

class AccountConfig(ConfigBase):
    ACC:str= Field(..., description="Email address of the qontext bot")
    EMAIL: str = Field(..., description="Email address of the qontext bot")
    PASSWORD: str = Field(..., description="Password of the qontext google account")

class BackendConfig(ConfigBase):
    BACKEND_URL: str = Field(..., description="Backed url of js")

class OpenAIConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    API_KEY: SecretStr = Field(
        ..., description="The API key for the OpenAI service"
    )

class DBConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="SQL_")
    USER: str
    PASSWORD: SecretStr
    NAME: str
    PORT: int
    HOST: str
    ECHO: bool = False


class Config(BaseSettings):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    db: DBConfig = Field(default_factory=DBConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)

    @classmethod
    def load_config(cls) -> "Config":
        return cls()



