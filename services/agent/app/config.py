from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    stage: str = "dev"

    service_name: str = "agent"
    service_version: str = "0.1.0"

    log_level: str = "INFO"

    database_url: str

    cerebras_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""

    cors_origins: str = "https://azref.ma,https://www.azref.ma,https://huquqai.com,https://www.huquqai.com,https://huquqai-beta.vercel.app"

    max_agent_steps: int = 5
    default_temperature: float = 0.3
    default_max_tokens: int = 3000

    @property
    def is_production(self) -> bool:
        return self.stage == "production"


settings = Settings()
