from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    gcp_project_id: str
    gcs_bucket_name: str
    firebase_project_id: str
    gemini_api_key: str
    resend_api_key: str = ""
    share_base_url: str = "http://localhost:3000"
    share_token_expiry_days: int = 7
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_monthly: str = ""
    stripe_price_id_annual: str = ""
    stripe_price_id_student: str = ""
    trial_days: int = 3
    trial_daily_simulation_limit: int = 3
    max_clinic_users: int = 5
    frontend_url: str = "http://localhost:3000"
    docs_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
