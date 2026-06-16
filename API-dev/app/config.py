from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="API_", env_file=".env", extra="ignore"
    )

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    cors_origins: str = "*"
    stock_ticker: str = "AAPL"
    index_ticker: str = "SPY"
    data_start_date: str = "2011-01-01"


settings = Settings()


def cors_origins_list() -> list[str]:
    raw = settings.cors_origins.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]
