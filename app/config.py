from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_vision_model: str = "llava:7b"
    app_host: str = "127.0.0.1"
    app_port: int = 8080
    hf_hub_offline: bool = True
    data_dir: Path = ROOT / "data"
    upload_dir: Path = ROOT / "data" / "uploads"
    work_dir: Path = ROOT / "data" / "work"
    kg_dir: Path = ROOT / "data" / "kg"
    retrieve_k: int = 5
    match_threshold: float = 0.35


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.work_dir.mkdir(parents=True, exist_ok=True)
settings.kg_dir.mkdir(parents=True, exist_ok=True)
