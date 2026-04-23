from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    github_webhook_secret: str
    github_app_id: str
    github_app_private_key: str
    github_installation_id: str
    # LLM Configuration
    llm_api_key: str
    llm_model_name: str = "llama-3.3-70b-versatile"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
