from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.minimax_client import MiniMaxAPIError


class AudioStorageService:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save_hex_audio(self, hex_audio: str) -> str:
        return self.save_hex_audio_with_meta(hex_audio)["audio_url"]

    def _sanitize_filename_part(self, part: str) -> str:
        import re
        # Remove characters that are invalid in filenames across OSes
        sanitized = re.sub(r'[\\/*?:"<>|]', "", part)
        return sanitized.strip().replace(" ", "_")

    def save_hex_audio_with_meta(
        self,
        hex_audio: str,
        song_title: str | None = None,
        style_id: str | None = None
    ) -> dict[str, Path | str]:
        sanitized_payload = hex_audio.strip().removeprefix("0x")
        try:
            audio_bytes = bytes.fromhex(sanitized_payload)
        except ValueError as exc:
            raise MiniMaxAPIError("invalid hex audio payload") from exc

        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        title_part = self._sanitize_filename_part(song_title or "Untitled")
        style_part = self._sanitize_filename_part(style_id or "Default")
        
        filename = f"{timestamp}_{title_part}({style_part}).mp3"
        file_path = self._output_dir / filename
        file_path.write_bytes(audio_bytes)
        return {
            "filename": filename,
            "audio_url": f"/static/audio/{filename}",
            "file_path": file_path,
        }

    def cleanup(self, retention_hours: int, max_files: int) -> int:
        files = sorted(
            [p for p in self._output_dir.glob("*.mp3") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        now_ts = datetime.utcnow().timestamp()
        removed = 0

        for idx, file_path in enumerate(files):
            if file_path.with_suffix(".lrc").exists() or file_path.with_suffix(".aligned.json").exists():
                continue
            age_seconds = max(0, now_ts - file_path.stat().st_mtime)
            too_old = age_seconds > retention_hours * 3600
            over_limit = idx >= max_files
            if too_old or over_limit:
                file_path.unlink(missing_ok=True)
                removed += 1
        return removed