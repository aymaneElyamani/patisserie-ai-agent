


from openai import OpenAI
from server.env import GROQ_API, URL_API



agentOpenAIClient = OpenAI(api_key=GROQ_API, base_url=URL_API)

