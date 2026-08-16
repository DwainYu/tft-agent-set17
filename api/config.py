from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "TFT Agent Set 17"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DB_PATH: str = "data/tft.db"
    JWT_SECRET: str = "dev-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    RIOT_API_KEY: str = ""
    SMS_PROVIDER: str = "mock"
    SMS_ACCESS_KEY: str = ""
    SMS_SECRET_KEY: str = ""
    SMS_SIGN_NAME: str = ""
    SMS_TEMPLATE_CODE: str = ""
    ASSETS_DIR: str = "asset/img"

    # ── RAG Engine ──────────────────────────────────────────────
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: str = "19530"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "tft_neo4j"
    EMBEDDING_MODEL: str = "models/models/Xorbits--bge-m3/snapshots/master"
    RERANKER_MODEL: str = "models/models/BAAI--bge-reranker-v2-m3"
    RAG_TOP_K: int = 5
    DEVICE: str = "cpu"
    # Half precision for GPU inference. Keep False on CPU (fp16 needs CUDA);
    # enabling it roughly halves VRAM usage so BGE-M3 + reranker fit in 6GB.
    USE_FP16: bool = False

    # ── Agent / LLM (W3) ───────────────────────────────────────
    # OpenAI-compatible endpoint (vLLM, Ollama, or OpenAI itself).
    # Leave OPENAI_API_BASE empty to use the rule-based planner fallback.
    OPENAI_API_BASE: str = ""
    OPENAI_API_KEY: str = "sk-placeholder"
    LLM_MODEL: str = "qwen2.5-14b-awq"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    # Agent loop guard: max planner→executor→critic iterations
    AGENT_MAX_ITERATIONS: int = 3
    # Checkpoint persistence (SQLite for dev, Postgres for prod)
    CHECKPOINT_DB: str = "data/checkpoints.db"
    # LangSmith tracing (set LANGCHAIN_TRACING_V2=true in .env to enable)
    LANGCHAIN_PROJECT: str = "tft-agent-set17"


@lru_cache
def get_settings() -> Settings:
    return Settings()
