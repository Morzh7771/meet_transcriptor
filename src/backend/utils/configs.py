from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class ConfigBase(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class GroqConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="GROQ_")
    API_KEY: SecretStr = Field(..., description="Groq API key (speech-to-text)")
    WHISPER_MODEL: str = Field(
        default="whisper-large-v3-turbo",
        description="whisper-large-v3-turbo (fast) or whisper-large-v3 (better accuracy, 10.3% WER)",
    )


class AwsConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="AWS_")
    ACCESS_KEY_ID: Optional[str] = Field(None, description="AWS access key")
    SECRET_ACCESS_KEY: Optional[str] = Field(None, description="AWS secret key")
    REGION: Optional[str] = Field(None, description="AWS region")
    S3_BUCKET: Optional[str] = Field(None, description="S3 bucket for transcripts (ai/meets/...)")
    S3_BUCKET_PUBLIC: Optional[str] = Field(None, description="S3 bucket (alias, used if S3_BUCKET not set)")

    def get_credentials(self) -> dict:
        if self.ACCESS_KEY_ID and self.SECRET_ACCESS_KEY:
            return {"aws_access_key_id": self.ACCESS_KEY_ID, "aws_secret_access_key": self.SECRET_ACCESS_KEY}
        return {}


class SlackConfig(ConfigBase):
    model_config = SettingsConfigDict(env_prefix="SLACK_")
    WEBHOOK_URL: Optional[str] = Field(None, description="Slack Incoming Webhook URL for notifications")


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq: GroqConfig = Field(default_factory=GroqConfig)
    aws: AwsConfig = Field(default_factory=AwsConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)

    @classmethod
    def load_config(cls) -> "Config":
        return cls()
