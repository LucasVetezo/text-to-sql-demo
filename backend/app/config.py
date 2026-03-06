"""
Application configuration using pydantic-settings.
Reads from environment variables and optional .env file.
Supports Docker secret file injection (OPENAI_API_KEY_FILE).
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file so it works regardless of
# which directory uvicorn / pytest is launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_api_key_file: str = ""        # Docker secret path fallback
    openai_model: str = "gpt-4o"
    openai_whisper_model: str = "whisper-1"

    # --- LangSmith ---
    langsmith_tracing: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "text-to-sql-demo-dev"

    # --- Database ---
    db_url: str = "sqlite+aiosqlite:///./data/seeds/dev.db"

    # --- MLflow ---
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "text-to-sql-demo"

    # --- App ---
    environment: str = "development"
    backend_url: str = "http://localhost:8000"
    secret_key: str = "change-me"
    allowed_origins: list[str] = [
        "http://localhost:8501",
        "http://frontend:8501",
    ]

    def model_post_init(self, __context: object) -> None:
        """Load API key from Docker secret file if set."""
        if self.openai_api_key_file:
            secret_path = Path(self.openai_api_key_file)
            if secret_path.exists():
                self.openai_api_key = secret_path.read_text().strip()

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


# Module-level singleton — import this everywhere
settings = Settings()
