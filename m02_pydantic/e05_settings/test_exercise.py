import os

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsError

from m02_pydantic.e05_settings import exercise
from m02_pydantic.e05_settings.exercise import (
    AppSettings,
    CorsSettings,
    DatabaseSettings,
    LLMSettings,
    ServerSettings,
    ServiceSettings,
    get_settings,
)

PREFIX = "BCAMP05_"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Hide any real BCAMP05_* variables and run every test in an empty directory."""
    for name in list(os.environ):
        if name.upper().startswith(PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    # Reset the Task 7 cache (if it exists yet) so tests never share settings.
    getattr(exercise.get_settings, "cache_clear", lambda: None)()
    yield
    getattr(exercise.get_settings, "cache_clear", lambda: None)()


def errors_of(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple, str]]:
    return [(e["loc"], e["type"]) for e in exc_info.value.errors()]


class TestTask1DatabaseSettings:
    def test_defaults(self):
        s = DatabaseSettings()
        assert (s.host, s.port, s.name, s.user, s.pool_size) == ("localhost", 5432, "app", "app", 5)
        assert s.password.get_secret_value() == ""

    def test_reads_prefixed_env_vars(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_DB_HOST", "db.internal")
        monkeypatch.setenv("BCAMP05_DB_PORT", "6543")
        monkeypatch.setenv("bcamp05_db_pool_size", "20")  # case-insensitive
        monkeypatch.setenv("HOST", "should-be-ignored")
        s = DatabaseSettings()
        assert (s.host, s.port, s.pool_size) == ("db.internal", 6543, 20)

    @pytest.mark.parametrize(("port", "error_type"), [("0", "greater_than_equal"), ("70000", "less_than_equal"), ("abc", "int_parsing")])
    def test_invalid_port(self, monkeypatch, port, error_type):
        monkeypatch.setenv("BCAMP05_DB_PORT", port)
        with pytest.raises(ValidationError) as exc_info:
            DatabaseSettings()
        assert errors_of(exc_info) == [(("port",), error_type)]

    def test_kwargs_win_over_env(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_DB_PORT", "6543")
        assert DatabaseSettings(port=1).port == 1

    def test_url(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_DB_PASSWORD", "hunter2")
        s = DatabaseSettings(user="svc", name="orders")
        assert s.url() == "postgresql+asyncpg://svc:***@localhost:5432/orders"
        assert s.url(hide_password=False) == "postgresql+asyncpg://svc:hunter2@localhost:5432/orders"


class TestTask2LLMSettings:
    def test_api_key_required(self):
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings()
        assert errors_of(exc_info) == [(("api_key",), "missing")]

    def test_reads_env_and_defaults(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_LLM_API_KEY", "sk-test-123")
        monkeypatch.setenv("BCAMP05_LLM_TEMPERATURE", "0.7")
        s = LLMSettings()
        assert isinstance(s.api_key, SecretStr)
        assert s.api_key.get_secret_value() == "sk-test-123"
        assert (s.model, s.temperature, s.request_timeout_s, s.max_retries) == ("gpt-4o-mini", 0.7, 30.0, 2)

    def test_secret_not_leaked(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_LLM_API_KEY", "sk-test-123")
        s = LLMSettings()
        assert s.api_key.get_secret_value() == "sk-test-123"
        for text in (repr(s), str(s), s.model_dump_json(), str(s.model_dump())):
            assert "sk-test-123" not in text
        assert '"api_key":"**********"' in s.model_dump_json()

    @pytest.mark.parametrize(
        ("name", "value", "error_type"),
        [
            ("BCAMP05_LLM_TEMPERATURE", "2.5", "less_than_equal"),
            ("BCAMP05_LLM_REQUEST_TIMEOUT_S", "0", "greater_than"),
            ("BCAMP05_LLM_MAX_RETRIES", "-1", "greater_than_equal"),
        ],
    )
    def test_ranges(self, monkeypatch, name, value, error_type):
        monkeypatch.setenv("BCAMP05_LLM_API_KEY", "k")
        monkeypatch.setenv(name, value)
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings()
        assert [t for _, t in errors_of(exc_info)] == [error_type]


class TestTask3AppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert (s.app_name, s.debug, s.db.host, s.db.port, s.cache.ttl_s) == ("bootcamp-api", False, "localhost", 5432, 300)

    def test_nested_delimiter(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_APP_DB__HOST", "db.internal")
        monkeypatch.setenv("BCAMP05_APP_DB__ECHO", "true")
        monkeypatch.setenv("BCAMP05_APP_CACHE__TTL_S", "60")
        s = AppSettings()
        assert (s.db.host, s.db.port, s.db.echo) == ("db.internal", 5432, True)
        assert (s.cache.url, s.cache.ttl_s) == ("redis://localhost:6379/0", 60)

    def test_section_as_json(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_APP_DB", '{"host": "json-host", "port": 15432}')
        s = AppSettings()
        assert (s.db.host, s.db.port) == ("json-host", 15432)

    @pytest.mark.parametrize(("raw", "expected"), [("1", True), ("yes", True), ("on", True), ("false", False), ("0", False)])
    def test_bool_parsing(self, monkeypatch, raw, expected):
        monkeypatch.setenv("BCAMP05_APP_DEBUG", raw)
        monkeypatch.setenv("BCAMP05_APP_APP_NAME", "svc")
        s = AppSettings()
        assert (s.debug, s.app_name) == (expected, "svc")

    def test_nested_error_location(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_APP_DB__PORT", "99999")
        with pytest.raises(ValidationError) as exc_info:
            AppSettings()
        assert errors_of(exc_info) == [(("db", "port"), "less_than_equal")]


class TestTask4CorsSettings:
    def test_defaults(self):
        s = CorsSettings()
        assert (s.allowed_origins, s.allowed_methods, s.max_age_s) == ([], ["GET"], 600)

    def test_json_list(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_CORS_ALLOWED_ORIGINS", '["https://a.io", "https://b.io"]')
        assert CorsSettings().allowed_origins == ["https://a.io", "https://b.io"]

    def test_invalid_json_list(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_CORS_ALLOWED_ORIGINS", "https://a.io,https://b.io")
        monkeypatch.setenv("BCAMP05_CORS_MAX_AGE_S", "60")
        with pytest.raises(SettingsError) as exc_info:  # not JSON -> cannot decode
            CorsSettings()
        assert "allowed_origins" in str(exc_info.value)

    def test_comma_separated_methods(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_CORS_ALLOWED_METHODS", "get, post,, delete ")
        assert CorsSettings().allowed_methods == ["GET", "POST", "DELETE"]

    def test_methods_kwarg_uppercased(self):
        assert CorsSettings(allowed_methods=["get", "Patch"]).allowed_methods == ["GET", "PATCH"]


class TestTask5DotEnv:
    def test_reads_dotenv_in_cwd(self, tmp_path):
        (tmp_path / ".env").write_text(
            "# service config\n"
            "BCAMP05_SVC_SERVICE_NAME=billing\n"
            'BCAMP05_SVC_QUEUE_URL="amqp://guest:guest@mq:5672//"\n'
            "BCAMP05_SVC_SENTRY_DSN=https://key@sentry.example/1\n"
        )
        s = ServiceSettings()
        assert (s.service_name, s.queue_url, s.concurrency) == ("billing", "amqp://guest:guest@mq:5672//", 4)
        assert s.sentry_dsn.get_secret_value() == "https://key@sentry.example/1"

    def test_missing_file_uses_defaults(self):
        s = ServiceSettings()
        assert (s.service_name, s.queue_url, s.concurrency, s.sentry_dsn) == ("worker", "memory://", 4, None)

    def test_unrelated_keys_ignored(self, tmp_path):
        (tmp_path / ".env").write_text("POSTGRES_PASSWORD=x\nOTHER_TOOL_TOKEN=y\nBCAMP05_SVC_CONCURRENCY=8\n")
        assert ServiceSettings().concurrency == 8

    def test_priority_kwargs_env_dotenv(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("BCAMP05_SVC_SERVICE_NAME=from-file\nBCAMP05_SVC_CONCURRENCY=2\n")
        monkeypatch.setenv("BCAMP05_SVC_SERVICE_NAME", "from-env")
        s = ServiceSettings()
        assert (s.service_name, s.concurrency) == ("from-env", 2)
        assert ServiceSettings(service_name="from-kwarg").service_name == "from-kwarg"

    def test_explicit_env_file(self, tmp_path):
        (tmp_path / ".env").write_text("BCAMP05_SVC_SERVICE_NAME=default-file\n")
        prod = tmp_path / "deploy" / "prod.env"
        prod.parent.mkdir()
        prod.write_text("BCAMP05_SVC_SERVICE_NAME=prod-file\nBCAMP05_SVC_CONCURRENCY=0\n")
        with pytest.raises(ValidationError) as exc_info:
            ServiceSettings(_env_file=prod)
        assert errors_of(exc_info) == [(("concurrency",), "greater_than_equal")]
        prod.write_text("BCAMP05_SVC_SERVICE_NAME=prod-file\n")
        assert ServiceSettings(_env_file=prod).service_name == "prod-file"


class TestTask6ServerSettings:
    def test_defaults(self):
        s = ServerSettings()
        assert (s.environment, s.host, s.port, s.log_level, s.debug) == ("dev", "127.0.0.1", 8000, "INFO", False)
        assert (s.public_url.scheme, s.public_url.host, s.public_url.port) == ("http", "localhost", 8000)

    def test_log_level_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_SRV_LOG_LEVEL", "debug")
        assert ServerSettings().log_level == "DEBUG"

    @pytest.mark.parametrize(
        ("name", "value", "error_type"),
        [
            ("BCAMP05_SRV_ENVIRONMENT", "production", "literal_error"),
            ("BCAMP05_SRV_LOG_LEVEL", "verbose", "literal_error"),
            ("BCAMP05_SRV_PUBLIC_URL", "not a url", "url_parsing"),
            ("BCAMP05_SRV_PUBLIC_URL", "localhost:8000", "url_scheme"),
            ("BCAMP05_SRV_PUBLIC_URL", "ftp://files.example", "url_scheme"),
            ("BCAMP05_SRV_PORT", "65536", "less_than_equal"),
        ],
    )
    def test_field_validation(self, monkeypatch, name, value, error_type):
        monkeypatch.setenv(name, value)
        with pytest.raises(ValidationError) as exc_info:
            ServerSettings()
        assert [t for _, t in errors_of(exc_info)] == [error_type]

    def test_prod_rules(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_SRV_ENVIRONMENT", "prod")
        monkeypatch.setenv("BCAMP05_SRV_PUBLIC_URL", "https://api.example.com")
        assert ServerSettings().public_url.host == "api.example.com"
        monkeypatch.setenv("BCAMP05_SRV_DEBUG", "true")
        with pytest.raises(ValidationError, match="debug must be off in prod"):
            ServerSettings()

    def test_prod_requires_https(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_SRV_ENVIRONMENT", "prod")
        with pytest.raises(ValidationError, match="public_url must use https in prod"):
            ServerSettings()
        monkeypatch.setenv("BCAMP05_SRV_ENVIRONMENT", "staging")
        assert ServerSettings().environment == "staging"


class TestTask7GetSettings:
    def test_returns_app_settings(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_APP_APP_NAME", "cached-app")
        s = get_settings()
        assert isinstance(s, AppSettings)
        assert s.app_name == "cached-app"

    def test_same_instance(self):
        assert get_settings() is get_settings()

    def test_cached_until_cleared(self, monkeypatch):
        monkeypatch.setenv("BCAMP05_APP_APP_NAME", "first")
        first = get_settings()
        monkeypatch.setenv("BCAMP05_APP_APP_NAME", "second")
        assert get_settings().app_name == "first"
        get_settings.cache_clear()
        assert get_settings().app_name == "second"
        assert get_settings() is not first
