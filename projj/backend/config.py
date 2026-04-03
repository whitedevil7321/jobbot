from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    debug: bool = False
    headless: bool = True
    scrape_interval_minutes: int = 1
    auto_apply: bool = True
    max_concurrent_applications: int = 2
    database_url: str = "sqlite:///./data/jobbot.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
