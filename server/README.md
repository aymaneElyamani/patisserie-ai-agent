# Pâtisserie Chatbot API

FastAPI and SQLModel backend for conversations and chatbot messages.

## Run the application

```bash
cd server
uv sync
uv run fastapi dev src/server/main.py
```

Alternatively, use the installed project script:

```bash
uv run server
```

The API documentation is available at <http://127.0.0.1:8000/docs>.

## Recipe images from the CSV

The recipe file uses the column name `photos` for one direct HTTPS image URL per
recipe. When local search finds a recipe, the server includes its `photos` value
in the model context as `Photo CSV`. The model then generates the corresponding
`<figure><img ...></figure>` in its HTML response. Before returning that HTML,
the HTML response.

## Configure Groq

Copy `.env.example` to `.env`, then replace the placeholder with your project
API key:

```dotenv
GROQ_API=your_groq_api_key
URL_API=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-120b
```

The server uses the OpenAI-compatible Groq endpoint. The model receives the
recent saved messages from the active conversation before generating the next
response.

## Run the tests

```bash
uv run python -m unittest test_api.py -v
```
