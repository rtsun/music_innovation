from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils import get_data_dir

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(get_data_dir() / ".env"), env_file_encoding="utf-8")

    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_base_url: str = Field(
        default="https://api.minimaxi.com",
        alias="MINIMAX_BASE_URL",
    )
    minimax_lyrics_endpoint: str = Field(
        default="/v1/lyrics_generation",
        alias="MINIMAX_LYRICS_ENDPOINT",
    )
    minimax_music_endpoint: str = Field(
        default="/v1/music_generation",
        alias="MINIMAX_MUSIC_ENDPOINT",
    )
    minimax_model: str = Field(default="music-2.6-free", alias="MINIMAX_MODEL")
    request_timeout_seconds: int = Field(default=120, alias="REQUEST_TIMEOUT_SECONDS")
    styles_config_path: Path = Field(default=get_data_dir() / "config" / "styles.yaml", alias="STYLES_CONFIG_PATH")
    audio_format: str = Field(default="mp3", alias="AUDIO_FORMAT")
    sample_rate: int = Field(default=44100, alias="AUDIO_SAMPLE_RATE")
    bitrate: int = Field(default=256000, alias="AUDIO_BITRATE")
    max_history_items: int = Field(default=20, alias="MAX_HISTORY_ITEMS")
    task_worker_count: int = Field(default=2, alias="TASK_WORKER_COUNT")
    cleanup_enabled: bool = Field(default=True, alias="CLEANUP_ENABLED")
    cleanup_interval_minutes: int = Field(default=30, alias="CLEANUP_INTERVAL_MINUTES")
    audio_retention_hours: int = Field(default=24, alias="AUDIO_RETENTION_HOURS")
    audio_max_files: int = Field(default=100, alias="AUDIO_MAX_FILES")
    alignment_enabled: bool = Field(default=True, alias="ALIGNMENT_ENABLED")
    alignment_language: str = Field(default="zh", alias="ALIGNMENT_LANGUAGE")

    # DEPRECATED — AI model settings; kept for backward compatibility with
    # existing .env files but no longer read by AlignmentService.
    huggingface_endpoint: str = Field(
        default="https://hf-mirror.com",
        alias="HUGGINGFACE_ENDPOINT",
    )
    alignment_offline_mode: bool = Field(default=False, alias="ALIGNMENT_OFFLINE_MODE")
    demucs_model: str = Field(default="mdx_q", alias="DEMUCS_MODEL")
    whisper_model: str = Field(default="medium", alias="WHISPER_MODEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()