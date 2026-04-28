from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.paths import STATIC_DIR
from app.routers.api import router as api_router
from app.routers.pages import router as pages_router
from app.settings import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(pages_router)
app.include_router(api_router)


@app.get("/healthz")
def healthcheck():
    return {"status": "ok", "app": settings.app_name}
