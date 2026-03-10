from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, AzureOpenAI
from src.config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL, OPENAI_API_KEY, DEPLOYMENT, AZURE_ENDPOINT, API_VERSION

def get_Ollamallm(temperature: float = 0.0):
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )

def get_OpenAIClient():
    return AzureChatOpenAI(
        azure_deployment=DEPLOYMENT,
        api_version=API_VERSION,
        azure_endpoint=AZURE_ENDPOINT
    )


