from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion central de la aplicacion, cargada desde variables de entorno (.env)."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    project_name: str = "GymKeep API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://gymkeep:gymkeep_password@localhost:5432/gymkeep"
    # URL publica del frontend: se usa para construir el enlace que codifica el QR de cada equipo.
    frontend_url: str = "http://localhost:5173"


settings = Settings()
