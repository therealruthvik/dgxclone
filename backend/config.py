from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    docker_base_image: str = "nvcr.io/nvidia/pytorch:24.01-py3"
    gpu_device_id: str = "0"
    k8s_namespace: str = "default"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
