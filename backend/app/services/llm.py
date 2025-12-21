from langchain_openai import ChatOpenAI
from backend.app.core.config import settings

def get_llm(model: str = "nvidia/nemotron-nano-9b-v2:free"):
    """
    Returns a configured LangChain ChatModel using OpenRouter.
    Using Gemini Flash 1.5 for speed and stability.
    """
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPEN_ROUTER_API_KEY,
        model=model,
        temperature=0,
        max_retries=3
    )
