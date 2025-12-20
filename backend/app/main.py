from fastapi import FastAPI
from backend.app.core.config import settings
from backend.app.db.arango import db
from backend.app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)

@app.on_event("startup")
async def startup_event():
    db.initialize()

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Cognitive Loom API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
