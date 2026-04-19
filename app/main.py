from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.alignment_service import AlignmentService
from app.services.history_service import HistoryService
from app.services.minimax_client import MiniMaxAPIError, MiniMaxClient
from app.services.music_service import AudioStorageService
from app.services.style_service import CustomStyleMode, StyleService
from app.services.task_queue import TaskProgressUpdater, TaskQueueService
from app.utils import get_app_dir, get_data_dir


logger = logging.getLogger(__name__)

APP_DIR = get_app_dir() / "app"
DATA_DIR = get_data_dir()

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

settings = get_settings()
style_service = StyleService(settings.styles_config_path)
minimax_client = MiniMaxClient(settings)
audio_storage = AudioStorageService(DATA_DIR / "static" / "audio")
history_service = HistoryService(DATA_DIR / "data" / "history.json", settings.max_history_items)
task_queue = TaskQueueService(worker_count=settings.task_worker_count)
alignment_service = AlignmentService(
    language=settings.alignment_language,
)
cleanup_loop_task: asyncio.Task[None] | None = None


class LyricsRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    style_id: str | None = None


class MusicRequest(BaseModel):
    lyrics: str = Field(min_length=1, max_length=3500)
    style_id: str | None = None
    custom_style_prompt: str | None = Field(default=None, max_length=500)
    custom_style_mode: str | None = Field(default=CustomStyleMode.APPEND, max_length=20)
    keyword: str | None = Field(default=None, max_length=200)
    song_title: str | None = Field(default=None, max_length=200)
    style_tags: str | None = Field(default=None, max_length=200)


async def _handle_lyrics_task(payload: dict, update_progress: TaskProgressUpdater) -> dict:
    if not settings.minimax_api_key or settings.minimax_api_key == "your_api_key_here":
        raise ValueError("请先在 exe 同级目录的 .env 文件中配置 MINIMAX_API_KEY，然后重启程序。")
    update_progress("歌词生成中")
    style = style_service.get_style(payload.get("style_id"))
    prompt = style_service.render_lyrics_prompt(style, payload["keyword"])
    response = await minimax_client.generate_lyrics(prompt)
    return {
        "song_title": response.get("song_title", ""),
        "style_tags": response.get("style_tags", ""),
        "lyrics": response.get("lyrics", ""),
    }


async def _handle_music_task(payload: dict, update_progress: TaskProgressUpdater) -> dict:
    if not settings.minimax_api_key or settings.minimax_api_key == "your_api_key_here":
        raise ValueError("请先在 exe 同级目录的 .env 文件中配置 MINIMAX_API_KEY，然后重启程序。")
    update_progress("歌曲生成中")
    style = style_service.get_style(payload.get("style_id"))
    custom_mode = (payload.get("custom_style_mode") or CustomStyleMode.APPEND).strip().lower()
    if custom_mode not in {CustomStyleMode.APPEND, CustomStyleMode.OVERRIDE}:
        raise ValueError("custom_style_mode must be append or override")
    final_music_prompt = style_service.compose_music_prompt(
        style=style,
        custom_style_prompt=payload.get("custom_style_prompt"),
        custom_style_mode=custom_mode,
    )
    response = await minimax_client.generate_music(
        lyrics=payload["lyrics"],
        music_prompt=final_music_prompt,
    )
    update_progress("音频已生成，正在写入文件")
    hex_audio = response.get("data", {}).get("audio", "")
    if not hex_audio:
        raise MiniMaxAPIError("music api returned empty audio payload")

    saved = audio_storage.save_hex_audio_with_meta(
        hex_audio,
        song_title=payload.get("song_title"),
        style_id=payload.get("style_id")
    )
    audio_url = str(saved["audio_url"])
    filename = str(saved["filename"])
    file_path = Path(saved["file_path"])

    lyrics_lrc_url = ""
    lyrics_json_url = ""
    lyrics_timeline: list[dict] = []
    alignment_mode = "disabled"
    alignment_error = ""
    if settings.alignment_enabled:
        update_progress("音频已生成，时间轴估算中")
        try:
            aligned = alignment_service.align_and_save(audio_path=file_path, lyrics=payload["lyrics"])
            alignment_mode = aligned.mode
            alignment_error = aligned.error
            lyrics_lrc_url = aligned.lrc_url
            lyrics_json_url = aligned.json_url
            lyrics_timeline = aligned.lines
            update_progress("时间轴估算完成")
        except Exception as exc:
            alignment_mode = "failed"
            alignment_error = f"{type(exc).__name__}: {exc}"
            update_progress(f"时间轴估算失败：{alignment_error[:100]}")
            logger.error(f"Alignment failed for {file_path}: {exc}", exc_info=True)

    history_service.append_music_record(
        keyword=payload.get("keyword"),
        style_id=payload.get("style_id"),
        custom_style_mode=custom_mode,
        custom_style_prompt=payload.get("custom_style_prompt"),
        input_song_title=payload.get("song_title"),
        style_tags=payload.get("style_tags"),
        lyrics=payload.get("lyrics"),
        output_song_title=payload.get("song_title"),
        audio_url=audio_url,
        filename=filename,
        lyrics_lrc_url=lyrics_lrc_url,
        lyrics_json_url=lyrics_json_url,
        alignment_mode=alignment_mode,
        alignment_error=alignment_error,
    )
    return {
        "audio_url": audio_url,
        "filename": filename,
        "lyrics_lrc_url": lyrics_lrc_url,
        "lyrics_json_url": lyrics_json_url,
        "lyrics_timeline": lyrics_timeline,
        "alignment_mode": alignment_mode,
        "alignment_error": alignment_error,
    }


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(max(1, settings.cleanup_interval_minutes) * 60)
        audio_storage.cleanup(
            retention_hours=max(1, settings.audio_retention_hours),
            max_files=max(1, settings.audio_max_files),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global cleanup_loop_task  # noqa: PLW0603
    task_queue.register_handler("lyrics", _handle_lyrics_task)
    task_queue.register_handler("music", _handle_music_task)
    await task_queue.start()
    if settings.cleanup_enabled:
        cleanup_loop_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        if cleanup_loop_task:
            cleanup_loop_task.cancel()
            await asyncio.gather(cleanup_loop_task, return_exceptions=True)
        await task_queue.stop()


app = FastAPI(title="Lyrics To Song Web", lifespan=lifespan)

import os
# Ensure user audio directory exists
os.makedirs(str(DATA_DIR / "static" / "audio"), exist_ok=True)
app.mount("/static/audio", StaticFiles(directory=str(DATA_DIR / "static" / "audio")), name="audio")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "styles": style_service.list_styles(),
            "default_style_id": style_service.default_style_id,
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    keyword: str = "",
    style_id: str = "",
    lyrics: str = "",
    title: str = "",
    style_tags: str = "",
    limit: int = 50,
) -> HTMLResponse:
    safe_limit = min(max(limit, 1), settings.max_history_items)
    items = history_service.query(
        keyword=keyword,
        style_id=style_id,
        lyrics=lyrics,
        title=title,
        style_tags=style_tags,
        limit=safe_limit,
    )
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "items": items,
            "filters": {
                "keyword": keyword,
                "style_id": style_id,
                "lyrics": lyrics,
                "title": title,
                "style_tags": style_tags,
                "limit": safe_limit,
            },
        },
    )


@app.post("/api/lyrics")
async def generate_lyrics(payload: LyricsRequest) -> dict:
    try:
        return await _handle_lyrics_task(payload.model_dump(), lambda _: None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MiniMaxAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/music")
async def generate_music(payload: MusicRequest) -> dict:
    try:
        return await _handle_music_task(payload.model_dump(), lambda _: None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MiniMaxAPIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/lyrics")
async def create_lyrics_task(payload: LyricsRequest) -> dict:
    try:
        task_id = task_queue.submit("lyrics", payload.model_dump())
        return {"task_id": task_id, "status": "queued"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/music")
async def create_music_task(payload: MusicRequest) -> dict:
    try:
        task_id = task_queue.submit("music", payload.model_dump())
        return {"task_id": task_id, "status": "queued"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/history/{filename}")
async def delete_history_record(filename: str) -> dict:
    # Also delete physical files
    file_path = DATA_DIR / "static" / "audio" / filename
    if file_path.exists():
        file_path.unlink()

    # Delete related files (lrc, json)
    for suffix in [".lrc", ".aligned.json"]:
        related = file_path.with_suffix(suffix)
        if related.exists():
            related.unlink()

    success = history_service.delete_record(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "success"}


@app.post("/api/history/{filename}/regenerate_lrc")
async def regenerate_lrc(filename: str) -> dict:
    items = history_service.list_recent()
    record = next((it for it in items if it["filename"] == filename), None)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    lyrics = record.get("lyrics")
    if not lyrics:
        raise HTTPException(status_code=400, detail="No lyrics to align")

    audio_path = DATA_DIR / "static" / "audio" / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        aligned = alignment_service.align_and_save(audio_path=audio_path, lyrics=lyrics)
        updates = {
            "lyrics_lrc_url": aligned.lrc_url,
            "lyrics_json_url": aligned.json_url,
            "alignment_mode": aligned.mode,
            "alignment_error": aligned.error,
        }
        history_service.update_record(filename, updates)
        return {
            "status": "success",
            "lyrics_lrc_url": aligned.lrc_url,
            "lyrics_json_url": aligned.json_url,
            "lyrics_timeline": aligned.lines,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Alignment failed: {exc}") from exc


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    try:
        return task_queue.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


@app.get("/api/history")
async def get_history(
    limit: int = 10,
    keyword: str = "",
    style_id: str = "",
    lyrics: str = "",
    title: str = "",
    style_tags: str = "",
) -> dict:
    safe_limit = min(max(limit, 1), settings.max_history_items)
    return {
        "items": history_service.query(
            keyword=keyword,
            style_id=style_id,
            lyrics=lyrics,
            title=title,
            style_tags=style_tags,
            limit=safe_limit,
        )
    }
