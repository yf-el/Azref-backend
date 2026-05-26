from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CrmConfig(BaseSettings):
    """Salesforce CRM adapter config, sourced from env vars at boot.

    Auth uses JWT Bearer Flow — no password, just a Consumer Key (from
    the External Client App), the integration user's username, and an
    RSA private key paired with the cert uploaded to SF.

    In Lambda, set `SF_PRIVATE_KEY_SSM_PARAM` to the name of an SSM
    Parameter Store SecureString holding the PEM — the loader fetches +
    decrypts it at startup. Locally, set `SF_PRIVATE_KEY_PATH` to a
    `.key` file and the loader reads it for you. `SF_PRIVATE_KEY` (raw
    PEM) is also accepted but avoid it for real deploys: CFN/env-var
    encoding mangles multi-line PEM.
    """

    model_config = SettingsConfigDict(
        env_prefix="SF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    consumer_key: str
    username: str
    private_key: str | None = None
    private_key_path: str | None = None
    private_key_ssm_param: str | None = None
    domain: Literal["login", "test"] = "login"
    external_id_field: str = "External_User_Id__c"

    @model_validator(mode="after")
    def _resolve_private_key(self) -> "CrmConfig":
        if self.private_key:
            return self
        if self.private_key_path:
            self.private_key = Path(self.private_key_path).expanduser().read_text()
            return self
        if self.private_key_ssm_param:
            import boto3  # lazy: keep local/test envs free of AWS deps

            self.private_key = boto3.client("ssm").get_parameter(
                Name=self.private_key_ssm_param, WithDecryption=True
            )["Parameter"]["Value"]
            return self
        raise ValueError(
            "One of SF_PRIVATE_KEY, SF_PRIVATE_KEY_PATH, "
            "SF_PRIVATE_KEY_SSM_PARAM must be set."
        )
