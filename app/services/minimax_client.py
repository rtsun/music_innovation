from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class MiniMaxAPIError(Exception):
    pass


class MiniMaxClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._headers = {
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        }

    async def generate_lyrics(self, prompt: str) -> dict[str, Any]:
        payload = {
            "mode": "write_full_song",
            "prompt": prompt,
        }
        return await self._post(self._settings.minimax_lyrics_endpoint, payload)

    async def generate_music(self, lyrics: str, music_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self._settings.minimax_model,
            "prompt": music_prompt,
            "lyrics": lyrics,
            "output_format": "hex",
            "audio_setting": {
                "sample_rate": self._settings.sample_rate,
                "bitrate": self._settings.bitrate,
                "format": self._settings.audio_format,
            },
        }
        return await self._post(self._settings.minimax_music_endpoint, payload)

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        timeout = httpx.Timeout(float(self._settings.request_timeout_seconds))
        async with httpx.AsyncClient(
            base_url=self._settings.minimax_base_url,
            headers=self._headers,
            timeout=timeout,
        ) as client:
            response = await client.post(endpoint, json=payload)
            if response.status_code != 200:
                raise MiniMaxAPIError(
                    f"minimax http {response.status_code}: {response.text}"
                )
            data = response.json()

        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            status_msg = base_resp.get("status_msg", "unknown minimax api error")
            raise MiniMaxAPIError(f"minimax status {status_code}: {status_msg}")
        return data