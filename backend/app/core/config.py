from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cognitive Loom"
    API_V1_STR: str = "/api/v1"
    
    # ArangoDB
    ARANGO_HOST: str = "http://localhost:8529"
    ARANGO_USERNAME: str = "root"
    ARANGO_PASSWORD: str = "test"
    ARANGO_DB_NAME: str = "cognitive_loom"
    
    # LLM
    OPEN_ROUTER_API_KEY: str


    class Config:
        env_file = ".env"

settings = Settings()
