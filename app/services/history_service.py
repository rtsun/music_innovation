from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryService:
    def __init__(self, history_path: Path, max_items: int) -> None:
        self._history_path = history_path
        self._max_items = max_items
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._history_path.exists():
            self._history_path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict[str, Any]]:
        raw = self._history_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self._history_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_music_record(
        self,
        *,
        keyword: str | None,
        style_id: str | None,
        custom_style_mode: str | None,
        custom_style_prompt: str | None,
        input_song_title: str | None,
        style_tags: str | None,
        lyrics: str | None,
        output_song_title: str | None,
        audio_url: str,
        filename: str,
        lyrics_lrc_url: str | None = None,
        lyrics_json_url: str | None = None,
        alignment_mode: str | None = None,
        alignment_error: str | None = None,
    ) -> None:
        items = self._load()
        items.insert(
            0,
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "keyword": keyword or "",
                "style_id": style_id or "",
                "custom_style_mode": custom_style_mode or "",
                "custom_style_prompt": (custom_style_prompt or "").strip(),
                "input_song_title": input_song_title or "",
                "style_tags": style_tags or "",
                "lyrics": lyrics or "",
                "output_song_title": output_song_title or input_song_title or "",
                "audio_url": audio_url,
                "filename": filename,
                "lyrics_lrc_url": lyrics_lrc_url or "",
                "lyrics_json_url": lyrics_json_url or "",
                "alignment_mode": alignment_mode or "",
                "alignment_error": alignment_error or "",
            },
        )
        self._save(items[: self._max_items])

    def list_recent(self, limit: int | None = None) -> list[dict[str, Any]]:
        items = self._load()
        if limit is None:
            return items[: self._max_items]
        return items[:limit]

    def query(
        self,
        *,
        keyword: str = "",
        style_id: str = "",
        lyrics: str = "",
        title: str = "",
        style_tags: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        items = self._load()
        keyword_q = keyword.strip().lower()
        style_q = style_id.strip().lower()
        lyrics_q = lyrics.strip().lower()
        title_q = title.strip().lower()
        tags_q = style_tags.strip().lower()

        def _match(item: dict[str, Any]) -> bool:
            if keyword_q and keyword_q not in str(item.get("keyword", "")).lower():
                return False
            if style_q and style_q not in str(item.get("style_id", "")).lower():
                return False
            if lyrics_q and lyrics_q not in str(item.get("lyrics", "")).lower():
                return False
            title_source = f"{item.get('input_song_title', '')} {item.get('output_song_title', '')}"
            if title_q and title_q not in title_source.lower():
                return False
            if tags_q and tags_q not in str(item.get("style_tags", "")).lower():
                return False
            return True

        matched = [it for it in items if _match(it)]
        if limit is None:
            return matched[: self._max_items]
        return matched[:limit]

    def delete_record(self, filename: str) -> bool:
        items = self._load()
        new_items = [it for it in items if it.get("filename") != filename]
        if len(new_items) == len(items):
            return False
        self._save(new_items)
        return True

    def update_record(self, filename: str, updates: dict[str, Any]) -> bool:
        items = self._load()
        found = False
        for it in items:
            if it.get("filename") == filename:
                it.update(updates)
                found = True
                break
        if found:
            self._save(items)
        return found