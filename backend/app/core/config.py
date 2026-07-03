import os
from functools import lru_cache
from pydantic import BaseModel, Field

class Settings(BaseModel):
    app_name: str = "Autonomous Multi-Agent Software Engineering Platform"
    environment: str = Field(default="development")
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:7b")
    database_url: str = Field(default="postgresql+psycopg2://postgres:postgres@localhost:5432/agentic_ai")
    vector_store_path: str = Field(default="./data/vector_store")
    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_seconds: int = Field(default=3600)
    refresh_token_ttl_seconds: int = Field(default=60 * 60 * 24 * 30)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="http://localhost:8000/auth/google/callback")
    frontend_url: str = Field(default="http://localhost:3000")
    redis_url: str = Field(default="redis://localhost:6379/0")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Upgrade standard Settings configuration loading to fetch keys from host environment
    return Settings(
        app_name=os.getenv("APP_NAME", "Autonomous Multi-Agent Software Engineering Platform"),
        environment=os.getenv("ENVIRONMENT", "development"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/agentic_ai"),
        vector_store_path=os.getenv("VECTOR_STORE_PATH", "./data/vector_store"),
        jwt_secret=os.getenv("JWT_SECRET", "dev-secret-change-me"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_ttl_seconds=int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "3600")),
        refresh_token_ttl_seconds=int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 30))),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"),
        frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )
