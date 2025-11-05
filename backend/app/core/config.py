"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project wide configuration."""

    app_name: str = "llm-finetune-platform"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/llmft"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    verification_code_expire_minutes: int = 10
    verification_attempt_limit: int = 5
    workspace_storage_root: str = "storage"
    max_dataset_size_bytes: int = 5 * 1024 * 1024 * 1024  # 5 GiB
    dataset_upload_chunk_size: int = 8 * 1024 * 1024  # 8 MiB
    celery_task_always_eager: bool = False
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    allow_parallel_gpu: bool = False
    max_training_gpus: int = 4
    training_gpu_queues: list[str] = [
        "default",
        "high-memory",
        "spot",
    ]
    inference_rate_limit_per_minute: int = 120
    inference_daily_quota: int = 10000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
