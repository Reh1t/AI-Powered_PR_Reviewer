from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    github_webhook_secret: str
    github_app_id: str
    github_app_private_key: str
    github_installation_id: str
    # LLM Configuration
    llm_api_key: str = "ollama"
    llm_model_name: str = "llama3.1-parallel"
    ollama_base_url: str = "http://localhost:11434/v1"
    
    # Database Configuration
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5435/pr_reviewer"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
