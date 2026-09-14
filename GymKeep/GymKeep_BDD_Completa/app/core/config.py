from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = "GymKeep API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg2://gymkeep:gymkeep_password@localhost:5432/gymkeep"
    )

    mongo_url: str = (
        "mongodb://gymkeep:gymkeep_mongo_password@localhost:27017/?authSource=admin"
    )
    mongo_db: str = "gymkeep_ai"

    frontend_url: str = "http://localhost:5173"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "gymkeep"
    s3_secret_key: str = "gymkeep_minio_password"
    s3_bucket: str = "gymkeep-evidencias"
    s3_region: str = "us-east-1"


settings = Settings()
