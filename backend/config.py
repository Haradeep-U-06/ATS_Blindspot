from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover - pydantic v1 compatibility
    from pydantic import BaseSettings
    SettingsConfigDict = None


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    gemini_api_key: Optional[str] = None
    gemini_structuring_model: str = "gemini-2.0-flash"
    gemini_evaluation_model: str = "gemini-2.0-flash"
    ollama_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"

    github_token: Optional[str] = None
    cloudinary_cloud_name: Optional[str] = None
    cloudinary_api_key: Optional[str] = None
    cloudinary_api_secret: Optional[str] = None

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "ats_db"

    faiss_index_dir: str = str(BASE_DIR / "faiss_index")
    log_level: str = "INFO"
    max_resume_size_bytes: int = 10 * 1024 * 1024
    api_timeout_seconds: float = 30.0
    rag_top_k: int = 5

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
