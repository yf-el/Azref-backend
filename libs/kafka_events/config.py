from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaConfig(BaseSettings):
    """Connection config for Confluent Cloud, sourced from env vars at boot.

    Env vars are injected by the per-service deploy.sh from SSM
    (/azref/<env>/shared/KAFKA_*). Locally they come from .env / direnv.
    The KAFKA_ prefix is automatic via env_prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bootstrap_servers: str
    api_key: str
    api_secret: str
    client_id: str = "azref-default"
