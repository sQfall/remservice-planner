from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REMSERVICE_")

    APP_NAME: str = "РемСервис-Планировщик"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.db"
    DEBUG: bool = True


settings = Settings()
