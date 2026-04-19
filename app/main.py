import os
# Ensure user audio directory exists
os.makedirs(str(DATA_DIR / "static" / "audio"), exist_ok=True)
app.mount("/static/audio", StaticFiles(directory=str(DATA_DIR / "static" / "audio")), name="audio")
# Only mount the internal static dir if it exists
if (APP_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")