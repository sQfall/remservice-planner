from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REMSERVICE_")

    APP_NAME: str = "РемСервис-Планировщик"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.db"
    DEBUG: bool = True

    # CORS настройки
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost,http://127.0.0.1"

    # OSRM настройки
    OSRM_BASE_URL: str = "https://router.project-osrm.org/route/v1/driving"
    OSRM_TIMEOUT: float = 5.0
    OSRM_MAX_RETRIES: int = 2
    OSRM_CONCURRENCY: int = 5
    OSRM_ENABLED: bool = True
    OSRM_MIN_INTERVAL: float = 0.05  # минимальный интервал между запросами (сек)
    OSRM_CACHE_SIZE: int = 1000  # размер LRU кэша

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
