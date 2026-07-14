from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Hybrid VAWT CAE Platform"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./vawt_platform.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://vawt-simulator-frontend.vercel.app",
    ]
    default_azimuth_stations: int = 60  # BEM angular resolution for API-triggered solves

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
