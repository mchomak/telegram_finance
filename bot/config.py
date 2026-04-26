from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    whisper_model: str = "base"
    database_url: str
    openai_api_key: str
    telegram_proxy: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
