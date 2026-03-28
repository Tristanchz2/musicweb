import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.db import check_db_connection, get_db
from app.models import Track
from app.schemas import TrackCreate, TrackResponse

from fastapi.responses import Response
from app.auth import verify_password, require_auth

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI()

MUSIC_STORAGE_PATH = os.getenv(
    "MUSIC_STORAGE_PATH",
    str(PROJECT_ROOT / "data" / "music"),
)
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE_PATH = BASE_DIR / "static" / "index.html"

@app.post("/auth/login")
def login(password: str = Form(...)):
    verify_password(password)

    response = Response(content="ok")
    response.set_cookie(
        key="session",
        value="authenticated",
        httponly=True,
    )
    return response

@app.post("/auth/logout")
def logout():
    response = Response(content="logged out")
    response.delete_cookie("session")
    return response


@app.get("/auth/status")
def auth_status(session: str | None = Cookie(default=None)):
    return {"status": "verified" if session == "authenticated" else "unverified"}

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    Path(MUSIC_STORAGE_PATH).mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if not INDEX_FILE_PATH.exists():
        raise HTTPException(status_code=404, detail="index file not found")
    return INDEX_FILE_PATH.read_text(encoding="utf-8")


@app.get("/health/db")
def db_health_check():
    try:
        check_db_connection()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"database connection failed: {str(e)}")


@app.get("/debug/tables")
def list_tables(db: Session = Depends(get_db)):
    result = db.execute(
        text("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """)
    )
    tables = [row[0] for row in result.fetchall()]
    return {"tables": tables}


@app.post("/tracks", response_model=TrackResponse)
def create_track(
    payload: TrackCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    track = Track(
        title=payload.title,
        artist=payload.artist,
        album=payload.album,
        file_path=payload.file_path,
        format=payload.format,
        duration_seconds=payload.duration_seconds,
        file_size=payload.file_size,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@app.get("/tracks", response_model=list[TrackResponse])
def list_tracks(db: Session = Depends(get_db)):
    tracks = db.query(Track).order_by(Track.id.desc()).all()
    return tracks


@app.get("/tracks/{track_id}", response_model=TrackResponse)
def get_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="track not found")
    return track


@app.post("/tracks/upload", response_model=TrackResponse)
def upload_track(
    file: UploadFile = File(...),
    title: str = Form(...),
    artist: str = Form(""),
    album: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is missing")

    original_name = Path(file.filename).name
    suffix = Path(original_name).suffix.lower()

    allowed_suffixes = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="unsupported file type")

    safe_filename = original_name
    destination_path = Path(MUSIC_STORAGE_PATH) / safe_filename

    counter = 1
    while destination_path.exists():
        destination_path = Path(MUSIC_STORAGE_PATH) / f"{Path(original_name).stem}_{counter}{suffix}"
        counter += 1

    try:
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    file_size = destination_path.stat().st_size

    track = Track(
        title=title,
        artist=artist or None,
        album=album or None,
        file_path=str(destination_path),
        format=suffix.lstrip("."),
        duration_seconds=None,
        file_size=file_size,
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    return track


@app.delete("/tracks/{track_id}")
def delete_track(
    track_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="track not found")

    file_path = Path(track.file_path)
    db.delete(track)
    db.commit()

    if file_path.exists():
        file_path.unlink()

    return {"status": "ok", "deleted_id": track_id}


@app.get("/tracks/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="track not found")

    file_path = Path(track.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="audio file not found")

    media_type_map = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
    }
    track_format = (track.format or file_path.suffix.lstrip(".")).lower()
    media_type = media_type_map.get(track_format, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
        content_disposition_type="inline",
    )


@app.get("/tracks/{track_id}/download")
def download_track(
    track_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="track not found")

    file_path = Path(track.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="audio file not found")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=file_path.name,
        content_disposition_type="attachment",
    )
