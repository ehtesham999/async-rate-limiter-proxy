from fastapi import FastAPI

from app.core.redis import lifespan
from app.routers import proxy


app = FastAPI(
    title="Smart API Gateway",
    lifespan=lifespan,
)

app.include_router(proxy.router)
