from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    OPENAI_API_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"
    OPENAI_MODEL: str = "gpt-4o"
    # Set to true in .env to log review context metadata (never logs user content)
    DEBUG_AI_PROMPT: bool = False


settings = Settings()
