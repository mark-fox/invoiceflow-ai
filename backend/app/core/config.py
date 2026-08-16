from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "InvoiceFlow AI"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://invoiceflow:invoiceflow@db:5432/invoiceflow"
    upload_dir: Path = Path("/app/uploads")
    frontend_origin: str = "http://localhost:5173"
    seed_demo_data: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

