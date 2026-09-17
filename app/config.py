from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    web_app_url: str = ""
    database_url: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "finance.db"


settings = Settings()
