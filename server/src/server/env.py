import os

from dotenv import load_dotenv


load_dotenv()


GROQ_API = os.getenv("GROQ_API")
URL_API = os.getenv("URL_API", "https://api.groq.com/openai/v1")

RECENT_MESSAGE_LIMIT = int(os.getenv("RECENT_MESSAGE_LIMIT", "8"))

IS_CSV_DATA_ACTIVE = os.getenv("IS_CSV_DATA_ACTIVE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
