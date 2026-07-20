from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import get_settings
from api.database import init_db
from api.routers import chat, auth, conversations, rag
from api.core.exceptions import AppException, app_exception_handler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    init_db()
    static_dir = Path(settings.ASSETS_DIR)
    if static_dir.exists():
        print(f"Static assets: {static_dir}")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Custom exception handler
app.add_exception_handler(AppException, app_exception_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static assets (served from asset/img/ in project root)
if Path(settings.ASSETS_DIR).exists():
    app.mount("/assets", StaticFiles(directory=settings.ASSETS_DIR), name="assets")

# Routers
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(rag.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
