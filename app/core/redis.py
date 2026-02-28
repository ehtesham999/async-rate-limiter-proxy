import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import REDIS_URL

redis_connection = None


def get_redis_connection():
    return redis_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_connection

    try:
        redis_connection = redis.from_url(
            REDIS_URL,
            decode_responses=False,
        )
        await redis_connection.ping()
        print("✅ Connected to Redis successfully!")

    except Exception as error:
        print(f"⚠️  Could not connect to Redis: {error}")
        print("   The server will start, but rate limiting will be disabled.")
        redis_connection = None

    yield

    if redis_connection is not None:
        await redis_connection.close()
        print("🔌 Redis connection closed.")
