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

    ADMIN_LOGIN: str = "admin"
    ADMIN_PASSWORD: str = "egolist2024"
    ADMIN_SECRET_KEY: str = "change-this-in-production"

    # Telegram user ID of the manager who receives live-chat messages.
    # Get it by messaging @userinfobot. Set to 0 to disable live chat.
    MANAGER_TELEGRAM_ID: int = 0

    # AI provider switching: "openai" | "groq" | "openrouter"
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-5-mini"
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
