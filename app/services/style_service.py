from __future__ import annotations

import enum
from pathlib import Path

import yaml


class CustomStyleMode(str, enum.Enum):
    APPEND = "append"
    OVERRIDE = "override"


class StyleService:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._styles: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            self._styles = []
            return
        with self.config_path.open("r", encoding="utf-8") as f:
            self._styles = yaml.safe_load(f) or []

    def list_styles(self) -> list[dict]:
        return self._styles

    @property
    def default_style_id(self) -> str | None:
        return self._styles[0]["style_id"] if self._styles else None

    def get_style(self, style_id: str | None) -> dict | None:
        if not style_id:
            return self._styles[0] if self._styles else None
        return next((s for s in self._styles if s["style_id"] == style_id), None)

    def render_lyrics_prompt(self, style: dict | None, keyword: str) -> str:
        if not style or "lyrics_prompt_template" not in style:
            return f"请以“{keyword}”为主题，写一首结构完整的歌词。"
        return style["lyrics_prompt_template"].replace("{keyword}", keyword)

    def compose_music_prompt(
        self,
        style: dict | None,
        custom_style_prompt: str | None,
        custom_style_mode: str = CustomStyleMode.APPEND,
    ) -> str:
        base_prompt = style["music_prompt"] if style and "music_prompt" in style else ""
        custom_prompt = (custom_style_prompt or "").strip()

        if custom_mode := CustomStyleMode(custom_style_mode):
            if custom_mode == CustomStyleMode.OVERRIDE:
                return custom_prompt if custom_prompt else base_prompt
            if custom_mode == CustomStyleMode.APPEND:
                if base_prompt and custom_prompt:
                    return f"{base_prompt}, {custom_prompt}"
                return base_prompt or custom_prompt

        return base_prompt