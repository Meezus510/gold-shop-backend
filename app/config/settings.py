from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MIN_SECRET_KEY_LEN = 32


class Settings(BaseSettings):
    """
    Settings are loaded in this priority order (highest wins):
      1. Real environment variables (set by Render dashboard in production)
      2. .env.local  — local developer overrides, never committed
      3. .env        — shared defaults / example values
    """

    model_config = SettingsConfigDict(
        # Later files override earlier files; real env vars override all files.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # CORS — comma-separated list of allowed origins
    # Example: "http://localhost:5500,https://your-site.netlify.app"
    ALLOWED_ORIGINS: str = "http://localhost:5500,http://localhost:3000,http://127.0.0.1:5500"

    # Cloudinary — image storage
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < _MIN_SECRET_KEY_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LEN} characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v


settings = Settings()

# Parse ALLOWED_ORIGINS into a list for FastAPI's CORSMiddleware
allowed_origins: list[str] = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
