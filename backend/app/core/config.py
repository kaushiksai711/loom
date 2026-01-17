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
    #OPEN_ROUTER_API_KEY: str
    GEMINI_API_KEY: str
    OPEN_ROUTER_API_KEY: str
    
    # Phase 13.5: Mastery Thresholds (configurable via env vars)
    MASTERY_THRESHOLD_LEARNING: float = 0.3    # Novice -> Learning
    MASTERY_THRESHOLD_PROFICIENT: float = 0.6  # Learning -> Proficient
    MASTERY_THRESHOLD_MASTERED: float = 0.9    # Proficient -> Mastered

    class Config:
        env_file = ".env"

settings = Settings()

