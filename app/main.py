from fastapi import FastAPI

from app.routers import proxy

app = FastAPI(
    title="Smart API Gateway",
    version="0.1.0",
)

app.include_router(proxy.router)
