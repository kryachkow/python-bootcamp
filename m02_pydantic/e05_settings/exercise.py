"""Exercise 2.5: application settings with ``pydantic-settings``.

Every settings class in this file uses an ``env_prefix`` that starts with
``BCAMP05_``, so your real environment variables (``DEBUG``, ``PORT``,
``DATABASE_URL``...) never leak into the tests. Run the tests with:

    uv run pytest m02_pydantic/e05_settings
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# ---------------------------------------------------------------------------
# Task 1: DatabaseSettings (env_prefix, defaults, coercion, constraints)
# ---------------------------------------------------------------------------
# Write ``DatabaseSettings(BaseSettings)`` with
# ``model_config = SettingsConfigDict(env_prefix="BCAMP05_DB_")``. Field
# ``port`` is then read from the env var ``BCAMP05_DB_PORT`` (names are
# case-insensitive by default). Env values are strings; Pydantic coerces them.
#
#   | field        | type          | default          | rule        |
#   |--------------|---------------|------------------|-------------|
#   | ``host``     | ``str``       | ``"localhost"``  |             |
#   | ``port``     | ``int``       | ``5432``         | 1..65535    |
#   | ``name``     | ``str``       | ``"app"``        |             |
#   | ``user``     | ``str``       | ``"app"``        |             |
#   | ``password`` | ``SecretStr`` | ``SecretStr("")``|             |
#   | ``pool_size``| ``int``       | ``5``            | >= 1        |
#
# and a method ``url(self, *, hide_password: bool = True) -> str`` returning
# ``"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"``, where
# ``{password}`` is ``"***"`` when ``hide_password`` is true (safe for logs)
# and the real password otherwise (for ``create_async_engine``).
#
# Keyword arguments win over env vars: ``DatabaseSettings(port=1)`` ignores
# ``BCAMP05_DB_PORT``.

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCAMP05_DB_")

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = "app"
    user: str = "app"
    password: SecretStr = SecretStr("")
    pool_size: int = Field(default=5, ge=1)

    def url(self, *, hide_password: bool = True) -> str:
        password = "***" if hide_password else self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"


# ---------------------------------------------------------------------------
# Task 2: LLMSettings (required settings, SecretStr)
# ---------------------------------------------------------------------------
# Write ``LLMSettings(BaseSettings)`` with ``env_prefix="BCAMP05_LLM_"``:
#
#   | field                 | type          | default          | rule        |
#   |-----------------------|---------------|------------------|-------------|
#   | ``api_key``           | ``SecretStr`` | REQUIRED         |             |
#   | ``model``             | ``str``       | ``"gpt-4o-mini"``|             |
#   | ``temperature``       | ``float``     | ``0.0``          | 0..2        |
#   | ``request_timeout_s`` | ``float``     | ``30.0``         | > 0         |
#   | ``max_retries``       | ``int``       | ``2``            | >= 0        |
#
# * A missing ``BCAMP05_LLM_API_KEY`` must fail at startup with a
#   ``ValidationError`` (type ``"missing"``), not later on the first request.
# * ``SecretStr`` keeps the key out of ``repr()``, ``str()``, logs and
#   ``model_dump_json()`` (all show ``"**********"``). Only
#   ``settings.api_key.get_secret_value()`` returns the real key.

class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCAMP05_LLM_")

    api_key: SecretStr
    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.0, ge=0, le=2)
    request_timeout_s: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)


# ---------------------------------------------------------------------------
# Task 3: AppSettings (nested config with env_nested_delimiter)
# ---------------------------------------------------------------------------
class DbConfig(BaseModel):
    """Given. A nested section: a plain ``BaseModel``, NOT a ``BaseSettings``."""

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    echo: bool = False


class CacheConfig(BaseModel):
    """Given."""

    url: str = "redis://localhost:6379/0"
    ttl_s: int = Field(default=300, ge=0)


# Write ``AppSettings(BaseSettings)`` with
# ``SettingsConfigDict(env_prefix="BCAMP05_APP_", env_nested_delimiter="__")``
# and the fields
#
#   * ``app_name: str = "bootcamp-api"``
#   * ``debug: bool = False``  (``"1"``, ``"true"``, ``"yes"``, ``"on"`` are true)
#   * ``db: DbConfig = DbConfig()``
#   * ``cache: CacheConfig = CacheConfig()``
#
# With the delimiter, ``BCAMP05_APP_DB__HOST=db.internal`` sets
# ``settings.db.host`` and ``BCAMP05_APP_CACHE__TTL_S=60`` sets
# ``settings.cache.ttl_s``; the other nested fields keep their defaults. A
# whole section can also be given as JSON: ``BCAMP05_APP_DB='{"host": "x"}'``.

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCAMP05_APP_", env_nested_delimiter="__")

    app_name: str = "bootcamp-api"
    debug: bool = False
    db: DbConfig = DbConfig()
    cache: CacheConfig = CacheConfig()


# ---------------------------------------------------------------------------
# Task 4: CorsSettings (lists from env vars)
# ---------------------------------------------------------------------------
# Write ``CorsSettings(BaseSettings)`` with ``env_prefix="BCAMP05_CORS_"``:
#
#   * ``allowed_origins: list[str] = []``: complex types (lists, dicts,
#     models) are read from env vars as JSON:
#     ``BCAMP05_CORS_ALLOWED_ORIGINS='["https://a.io", "https://b.io"]'``.
#   * ``allowed_methods: Annotated[list[str], NoDecode] = ["GET"]``: ops
#     people prefer ``BCAMP05_CORS_ALLOWED_METHODS=get, post``. ``NoDecode``
#     turns off the JSON decoding for this field, so a
#     ``@field_validator("allowed_methods", mode="before")`` receives the raw
#     string: split it on ``","``, strip the parts, drop empty ones, and
#     uppercase them. A real list (e.g. passed as a keyword argument) is
#     uppercased too.
#   * ``max_age_s: int = 600``
#
# A value that is not valid JSON in ``BCAMP05_CORS_ALLOWED_ORIGINS`` makes
# ``CorsSettings()`` raise ``pydantic_settings.SettingsError`` (a ``ValueError``).

class CorsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCAMP05_CORS_")

    allowed_origins: list[str] = []
    allowed_methods: Annotated[list[str], NoDecode] = ["GET"]
    max_age_s: int = 600

    @field_validator("allowed_methods", mode="before")
    @classmethod
    def _split_methods(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [str(m).strip().upper() for m in value if str(m).strip()]
        return value


# ---------------------------------------------------------------------------
# Task 5: ServiceSettings (.env files)
# ---------------------------------------------------------------------------
# Write ``ServiceSettings(BaseSettings)`` that also reads a ``.env`` file:
#
#   * ``SettingsConfigDict(env_prefix="BCAMP05_SVC_", env_file=".env",
#     env_file_encoding="utf-8", extra="ignore")``
#       - ``env_file=".env"`` is resolved against the CURRENT WORKING DIRECTORY;
#         a missing file is simply skipped.
#       - ``extra="ignore"`` matters: a shared ``.env`` usually holds keys for
#         other tools too, and ``BaseSettings`` defaults to ``extra="forbid"``,
#         which would reject them.
#   * fields: ``service_name: str = "worker"``, ``queue_url: str = "memory://"``,
#     ``concurrency: int = 4`` (>= 1), ``sentry_dsn: SecretStr | None = None``
#
# Priority, highest first: keyword arguments, environment variables, the
# ``.env`` file, field defaults. A different file can be chosen per call:
# ``ServiceSettings(_env_file="deploy/prod.env")``.

class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BCAMP05_SVC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "worker"
    queue_url: str = "memory://"
    concurrency: int = Field(default=4, ge=1)
    sentry_dsn: SecretStr | None = None


# ---------------------------------------------------------------------------
# Task 6: ServerSettings (validating settings)
# ---------------------------------------------------------------------------
# Bad config should crash the process at startup with a clear message. Write
# ``ServerSettings(BaseSettings)`` with ``env_prefix="BCAMP05_SRV_"``:
#
#   | field           | type                                   | default                     |
#   |-----------------|----------------------------------------|-----------------------------|
#   | ``environment`` | ``Literal["dev", "staging", "prod"]``  | ``"dev"``                   |
#   | ``host``        | ``str``                                | ``"127.0.0.1"``             |
#   | ``port``        | ``int``, 1..65535                      | ``8000``                    |
#   | ``public_url``  | ``HttpUrl``                            | ``"http://localhost:8000"`` |
#   | ``log_level``   | ``Literal["DEBUG", "INFO", "WARNING", "ERROR"]`` | ``"INFO"``        |
#   | ``debug``       | ``bool``                               | ``False``                   |
#
#   * ``log_level`` is case-insensitive: a before ``field_validator``
#     uppercases strings (``"debug"`` -> ``"DEBUG"``).
#   * an after ``model_validator`` enforces two production rules:
#       - ``environment == "prod"`` and ``debug`` -> ``ValueError("debug must be off in prod")``
#       - ``environment == "prod"`` and ``public_url.scheme != "https"`` ->
#         ``ValueError("public_url must use https in prod")``
#
# Hint: declare the default as ``HttpUrl("http://localhost:8000")``.
# ``HttpUrl`` accepts only ``http``/``https``: ``"ftp://..."`` and even
# ``"localhost:8000"`` (parsed as scheme ``localhost``) fail with ``"url_scheme"``.

class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BCAMP05_SRV_")

    environment: Literal["dev", "staging", "prod"] = "dev"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    public_url: HttpUrl = HttpUrl("http://localhost:8000")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _production_rules(self) -> Self:
        if self.environment == "prod":
            if self.debug:
                raise ValueError("debug must be off in prod")
            if self.public_url.scheme != "https":
                raise ValueError("public_url must use https in prod")
        return self


# ---------------------------------------------------------------------------
# Task 7: a cached get_settings()
# ---------------------------------------------------------------------------
# Write a module-level function ``get_settings() -> AppSettings`` that builds
# ``AppSettings()`` ONCE and returns the same object on every later call.
# Decorate it with ``@lru_cache`` (``functools.lru_cache``): this is the
# standard FastAPI pattern (``Depends(get_settings)``), and it gives you
# ``get_settings.cache_clear()`` for tests that change env vars.
#
# >>> get_settings() is get_settings()
# True

@lru_cache
def get_settings() -> AppSettings:
    """Return the process-wide ``AppSettings``, built on first use."""
    return AppSettings()
