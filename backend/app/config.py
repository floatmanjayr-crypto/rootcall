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
    TELNYX_SIP_USERNAME: str = os.getenv("TELNYX_SIP_USERNAME", "")
    TELNYX_SIP_PASSWORD: str = os.getenv("TELNYX_SIP_PASSWORD", "")
    TELNYX_OUTBOUND_VOICE_PROFILE_ID: str = os.getenv("TELNYX_OUTBOUND_VOICE_PROFILE_ID", "")

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
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", ""))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Email (SendGrid) — transactional mail such as password resets.
    # Password recovery requires a configured provider and public application URL.
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "no-reply@rootcall.ai")

    # Public base URL used to build links in emails (e.g. https://app.rootcall.ai).
    # Falls back to Render's own public URL so checkout returns never point at a stale domain.
    APP_BASE_URL: str = os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    
    # ✅ Backward compatibility alias
    @property
    def SECRET_KEY(self):
        return self.JWT_SECRET_KEY
    
    @property
    def ALGORITHM(self):
        return self.JWT_ALGORITHM

settings = Settings()