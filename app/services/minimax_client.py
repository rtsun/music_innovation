import httpx

from app.config import Settings


class MiniMaxAPIError(Exception):
    pass


class MiniMaxClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.minimax_base_url,
            timeout=settings.request_timeout_seconds,
        )

    async def generate_lyrics(self, prompt: str) -> dict:
        url = self.settings.minimax_lyrics_endpoint
        headers = {
            "Authorization": f"Bearer {self.settings.minimax_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.minimax_model,
            "prompt": prompt,
        }
        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise MiniMaxAPIError(f"Lyrics generation failed: {exc}") from exc

    async def generate_music(self, lyrics: str, music_prompt: str) -> dict:
        url = self.settings.minimax_music_endpoint
        headers = {
            "Authorization": f"Bearer {self.settings.minimax_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.minimax_model,
            "lyrics": lyrics,
            "music_prompt": music_prompt,
            "audio_format": self.settings.audio_format,
            "sample_rate": self.settings.sample_rate,
            "bitrate": self.settings.bitrate,
        }
        try:
            resp = await self.client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            raise MiniMaxAPIError(f"Music generation failed: {exc}") from exc
