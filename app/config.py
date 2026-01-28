import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://fcc:fcc_secure_password@db:5432/fccdb"

    # API
    api_interface: str = "0.0.0.0"
    api_port: int = 8010

    # Auto-update
    auto_update_days: int = 7

    # FCC Data URL
    fcc_data_url: str = "https://data.fcc.gov/download/pub/uls/complete/l_amat.zip"

    # Temp directory for downloads
    temp_dir: str = "/tmp/fcc_data"

    # Batch size for database inserts
    db_chunk_size: int = 100000

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
