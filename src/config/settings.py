import os
from dotenv import load_dotenv

load_dotenv()

# Database
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "54322")
DB_DBNAME = os.getenv("DB_DBNAME", "postgres")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_DBNAME}"
)

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# AzureOpenAi
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEPLOYMENT = os.getenv("DEPLOYMENT")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
API_VERSION = os.getenv("API_VERSION")

# TAVILY
TAVILY_API = os.getenv("TAVILY_API")

# Worker polling interval 
WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "10"))


# LANGSMITH TRACING
LANGSMITH_TRACING=os.getenv("LANGSMITH_TRACING")
LANGSMITH_API_KEY=os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT=os.getenv("LANGSMITH_PROJECT")
LANGSMITH_ENDPOINT=os.getenv("LANGSMITH_ENDPOINT")