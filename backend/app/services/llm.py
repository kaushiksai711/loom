from langchain_openai import ChatOpenAI
from backend.app.core.config import settings

# def get_llm(model: str = "google/gemini-2.0-flash-exp:free"):
#     """
#     Returns a configured LangChain ChatModel using OpenRouter.
#     Using Gemini 2.0 Flash (Experimental) for SOTA extraction quality.
#     """
#     return ChatOpenAI(
#         base_url="https://openrouter.ai/api/v1",
#         api_key=settings.OPEN_ROUTER_API_KEY,
#         model=model,
#         temperature=0,
#         max_retries=3
#     )
from langchain_google_genai import ChatGoogleGenerativeAI


def get_llm(model: str = "gemini-2.5-flash"):
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0,
        max_retries=2,
    )
