
import json
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Dict, Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.backend import db

class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

# class AccountConfig(ConfigBase):
#     # ACC:str= Field(..., description="Email address of the qontext bot")
#     EMAIL: str = Field(..., description="Email address of the qontext bot")
#     PASSWORD: str = Field(..., description="Password of the qontext google account")

class BackendConfig(ConfigBase):
    BACKEND_URL: str = Field(..., description="Backed url of js")

class OpenAIConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    API_KEY: SecretStr = Field(
        ..., description="The API key for the OpenAI service"
    )

class VectorDBConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")
    URL: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    API_KEY: Optional[SecretStr] = Field(default=None, description="API key for Qdrant (optional for local)")


class DBConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="SQL_")
    USER: str
    PASSWORD: SecretStr
    NAME: str
    PORT: int
    HOST: str
    ECHO: bool = False
    @property
    def connection_url(self) -> str:
        """Generate SQLAlchemy connection URL"""
        return f"mysql+pymysql://{self.USER}:{self.PASSWORD.get_secret_value()}@{self.HOST}:{self.PORT}/{self.NAME}?charset=utf8mb4"
    
class VectorDBConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="QDRANT_")
    URL: str
    API_KEY: SecretStr
    
class LinkedinParserConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="GENERECT_")
    API_KEY: SecretStr

class LawParserConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="CONGRESS_")
    API_KEY: SecretStr

class GoogleSearchConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")
    SEARCH_ENGINE_ID: str
    API_KEY: SecretStr

class FilterConfig(ConfigBase):
    exp_multiplier: int = Field(default=2)
    exp_max_wait_time: int = Field(default=60)
    exp_max_retries: int = Field(default=3)
    batch_size: int = Field(default=10)
    model_name: str = Field(default="gpt-4o-mini")

class ScrapperConfig(ConfigBase):
    base_delay: int = Field(default=2)
    max_delay: int = Field(default=30)
    max_retries: int = Field(default=3)
    timeout_extra_retries: int = Field(default=2)
    headless: bool = Field(default=True)


class Config(BaseSettings):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    vectordb: VectorDBConfig = Field(default_factory=VectorDBConfig)
    db: DBConfig = Field(default_factory=DBConfig)
    vectordb: VectorDBConfig = Field(default_factory=VectorDBConfig)
    linkedinparser: LinkedinParserConfig = Field(default_factory=LinkedinParserConfig)
    lawparser: LawParserConfig = Field(default_factory=LawParserConfig)
    searcher: GoogleSearchConfig = Field(default_factory=GoogleSearchConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    scraper: ScrapperConfig = Field(default_factory=ScrapperConfig)
    # account: AccountConfig = Field(default_factory=AccountConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)

    @classmethod
    def load_config(cls) -> "Config":
        return cls()
