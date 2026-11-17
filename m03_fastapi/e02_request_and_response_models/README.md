# 3.2 Request and response models

Pydantic models are the contract at your API boundary. One model describes
what a client may send, a different model describes what you return, and
FastAPI validates both. This exercise keeps a password from leaking out of
a signup API and builds an OpenAI-style chat endpoint with nested,
constrained models.

## Concepts

| Tool | What it does |
|------|--------------|
| `def create(user: UserIn)` | a Pydantic-typed parameter is read from the JSON body |
| `response_model=UserOut` | the return value is validated and filtered through `UserOut`, so fields it does not declare (such as `hashed_password`) are dropped |
| `-> ChatResponse` | the return annotation works as the response model when you return that model |
| `status_code=201`, `response: Response` | the default status code; setting headers such as `Location` |
| `Annotated[int, Path(ge=1)]`, `Annotated[int, Query(ge=1, le=100)]` | constraints checked before your code runs; a violation gives `422` |
| `response_model_exclude_none=True` | leaves `null` fields out of the JSON |
| two `Body()` parameters | FastAPI expects `{"old_password": ..., "new_password": ...}` |
| `SecretStr` | the value is masked in `repr` and logs; read it with `.get_secret_value()` |

FastAPI's `422` body is a list of errors, and each error has a `loc` such as
`["body", "password"]` or `["query", "limit"]`. Clients use it to point at
the field that failed. Exercise 3.4 shows how to change this format.

## Tasks

All tasks are in [`exercise.py`](exercise.py). The in-memory `UserStore` is given.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `UserIn`, `UserOut` | separate input and output schemas, `Field` constraints, `SecretStr` |
| 2 | `POST /users` | `201`, `response_model` filtering, `Location` header, `409`, `422` |
| 3 | `GET /users/{user_id}` | `Path(ge=1)` in `Annotated` style, `response_model_exclude_none` |
| 4 | `GET /users` | returning `list[UserOut]`, `Query` constraints (`ge`, `le`, `max_length`) |
| 5 | `POST /users/{user_id}/password` | several body parameters, `403` vs `404`, `204` |
| 6 | `ChatMessage`, `ChatRequest` | nested models, `Literal`, list and number constraints |
| 7 | `POST /chat/completions` | a return-annotation response model, a fake LLM with token usage |

## Run the tests

```bash
uv run pytest m03_fastapi/e02_request_and_response_models
uv run pytest m03_fastapi/e02_request_and_response_models -k Task2   # one task only
```

## Further reading

- [Response model: return type](https://fastapi.tiangolo.com/tutorial/response-model/)
- [Query parameters and string validations](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/)
