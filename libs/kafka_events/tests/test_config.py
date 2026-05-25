import pytest
from pydantic import ValidationError

from kafka_events.config import KafkaConfig


@pytest.fixture
def env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    # Isolate from any .env file the test runner might pick up.
    monkeypatch.delenv("KAFKA_CLIENT_ID", raising=False)
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "pkc-x.eu-west-1.aws.confluent.cloud:9092")
    monkeypatch.setenv("KAFKA_API_KEY", "test-key")
    monkeypatch.setenv("KAFKA_API_SECRET", "test-secret")


class TestKafkaConfigFromEnv:
    def test_reads_all_required_from_env(self, env_set: None) -> None:
        config = KafkaConfig()
        assert config.bootstrap_servers == "pkc-x.eu-west-1.aws.confluent.cloud:9092"
        assert config.api_key == "test-key"
        assert config.api_secret == "test-secret"

    def test_client_id_default(self, env_set: None) -> None:
        config = KafkaConfig()
        assert config.client_id == "azref-default"

    def test_client_id_override_via_argument(self, env_set: None) -> None:
        config = KafkaConfig(client_id="azref-agent")
        assert config.client_id == "azref-agent"

    def test_client_id_override_via_env(
        self, env_set: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAFKA_CLIENT_ID", "azref-from-env")
        config = KafkaConfig()
        assert config.client_id == "azref-from-env"

    def test_argument_takes_precedence_over_env(
        self, env_set: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAFKA_CLIENT_ID", "from-env")
        config = KafkaConfig(client_id="from-arg")
        assert config.client_id == "from-arg"

    def test_missing_var_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
        monkeypatch.delenv("KAFKA_API_KEY", raising=False)
        monkeypatch.delenv("KAFKA_API_SECRET", raising=False)
        # Make sure no local .env supplies the values either.
        monkeypatch.chdir("/tmp")
        with pytest.raises(ValidationError):
            KafkaConfig()

    def test_extra_kafka_env_vars_ignored(
        self, env_set: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # extra="ignore" — unknown KAFKA_* env vars must not crash construction.
        monkeypatch.setenv("KAFKA_SOMETHING_UNRELATED", "whatever")
        KafkaConfig()  # no raise


class TestExplicitConstruction:
    def test_constructor_accepts_explicit_kwargs(self) -> None:
        config = KafkaConfig(
            bootstrap_servers="x",
            api_key="k",
            api_secret="s",
            client_id="azref-agent",
        )
        assert config.bootstrap_servers == "x"
        assert config.client_id == "azref-agent"
