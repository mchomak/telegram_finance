from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    openai_api_key: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
