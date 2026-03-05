from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class OpenAIConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="OPENAI_")
    API_KEY: SecretStr = Field(..., description="OpenAI API key (for LLM, e.g. instructor)")


class GroqConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="GROQ_")
    API_KEY: SecretStr = Field(..., description="Groq API key (speech-to-text)")


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    groq: GroqConfig = Field(default_factory=GroqConfig)

    @classmethod
    def load_config(cls) -> "Config":
        return cls()
