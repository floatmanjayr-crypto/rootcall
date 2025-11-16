import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # App Info
    APP_NAME: str = "VoIP Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    ALLOWED_ORIGINS: list = ["*"]

    # Telnyx
    TELNYX_API_KEY: str = os.getenv("TELNYX_API_KEY", "")
    TELNYX_PUBLIC_KEY: str = os.getenv("TELNYX_PUBLIC_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./voip.db")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Retell.ai
    RETELL_API_KEY: str = os.getenv("RETELL_API_KEY", "")

    # Deepgram
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")

    # Cloudflare R2 (optional)
    CLOUDFLARE_ACCOUNT_ID: str = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    CLOUDFLARE_R2_ACCESS_KEY_ID: str = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "")
    CLOUDFLARE_R2_SECRET_ACCESS_KEY: str = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "")
    CLOUDFLARE_R2_BUCKET_NAME: str = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "")
    CLOUDFLARE_R2_PUBLIC_URL: str = os.getenv("CLOUDFLARE_R2_PUBLIC_URL", "")

    # JWT/Auth - ✅ Now reads JWT_SECRET_KEY from Render environment
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "your-secret-key-change-in-production"))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # ✅ Backward compatibility alias
    @property
    def SECRET_KEY(self):
        return self.JWT_SECRET_KEY
    
    @property
    def ALGORITHM(self):
        return self.JWT_ALGORITHM

settings = Settings()