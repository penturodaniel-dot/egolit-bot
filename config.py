from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    OPENAI_API_KEY: str

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    MEDIA_BASE_URL: str = "http://api.egolist.com.ua"
    DEFAULT_CITY_ID: int = 133
    DEFAULT_CITY_NAME: str = "Дніпро"

    class Config:
        env_file = ".env"


settings = Settings()
