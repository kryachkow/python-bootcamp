# 2.5 Settings with `pydantic-settings`

A twelve-factor service reads its configuration from environment variables
and, locally, from a `.env` file. `pydantic-settings` turns that into a typed,
validated object, so a typo in `DATABASE_PORT` crashes the process at startup
instead of surfacing at 3 a.m. This exercise builds the settings layer of a
typical FastAPI + async SQLAlchemy + LLM backend.

## Concepts

| Tool | Use it for |
|------|------------|
| `class S(BaseSettings)` | fields are filled from env vars, then validated like any model |
| `SettingsConfigDict(env_prefix="APP_")` | namespacing: field `port` reads `APP_PORT` (case-insensitive) |
| `env_nested_delimiter="__"` | `APP_DB__HOST` sets `settings.db.host` (nested `BaseModel` sections) |
| `SecretStr` | API keys and passwords hidden in `repr`, logs and dumps; `.get_secret_value()` to use them |
| complex fields (`list`, `dict`, models) | parsed from env vars as JSON |
| `Annotated[list[str], NoDecode]` + before validator | accept `a,b,c` instead of JSON |
| `env_file=".env"`, `extra="ignore"` | local development; `S(_env_file=path)` picks another file |
| `HttpUrl`, `Literal`, `Field(ge=, le=)`, `model_validator` | reject bad config at startup |
| `@lru_cache def get_settings()` | one settings object per process; `cache_clear()` in tests |

Priority, highest first: keyword arguments to the constructor, environment
variables, the `.env` file, secrets directory, field defaults.

## Tasks

All tasks are in [`exercise.py`](exercise.py). Every class uses a prefix
starting with `BCAMP05_`, and the tests remove all `BCAMP05_*` variables and
run in a temporary directory, so your own environment and `.env` files never
affect the result.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `DatabaseSettings` | `env_prefix`, defaults, coercion, constraints, building a DSN |
| 2 | `LLMSettings` | required settings, `SecretStr`, not leaking secrets |
| 3 | `AppSettings` | nested sections with `env_nested_delimiter`, booleans from env |
| 4 | `CorsSettings` | JSON lists from env, `NoDecode` + comma-separated values |
| 5 | `ServiceSettings` | `.env` files, `extra="ignore"`, source priority, `_env_file` |
| 6 | `ServerSettings` | `HttpUrl`, `Literal`, port ranges, production-only rules |
| 7 | `get_settings` | `functools.lru_cache`, `cache_clear()` |

## Run the tests

```bash
uv run pytest m02_pydantic/e05_settings
uv run pytest m02_pydantic/e05_settings -k Task5   # one task only
```

In FastAPI you would then inject the settings with
`settings: Annotated[AppSettings, Depends(get_settings)]` and replace them in
tests with `app.dependency_overrides[get_settings] = lambda: AppSettings(...)`.

## Further reading

- [Settings management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI: settings and environment variables](https://fastapi.tiangolo.com/advanced/settings/)
