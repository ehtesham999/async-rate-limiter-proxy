import time
import uuid
from app.core.config import RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
from app.core.redis import get_redis_connection


async def check_rate_limit(client_ip: str):
    redis_client = get_redis_connection()

    if redis_client is None:
        print("Redis not available — skipping rate limit check.")
        return {
            "allowed": True,
            "current_count": 0,
            "max_requests": RATE_LIMIT_MAX_REQUESTS,
            "retry_after": 0,
        }

    redis_key = f"rate_limit:{client_ip}"

    now = time.time()
    window_cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    request_id = str(uuid.uuid4())

    try:
        pipe = redis_client.pipeline()

        pipe.zremrangebyscore(redis_key, 0, window_cutoff)

        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {request_id: now})

        pipe.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS)
        results = await pipe.execute()

    except Exception as error:
        print(f" Redis error during rate limit check: {error}")
        return {
            "allowed": True,
            "current_count": 0,
            "max_requests": RATE_LIMIT_MAX_REQUESTS,
            "retry_after": 0,
        }

    current_request_count = results[1]

    is_allowed = current_request_count < RATE_LIMIT_MAX_REQUESTS

    if is_allowed:
        return {
            "allowed": True,
            "current_count": current_request_count + 1,
            "max_requests": RATE_LIMIT_MAX_REQUESTS,
        }

    try:
        await redis_client.zrem(redis_key, request_id)
        oldest_entries = await redis_client.zrange(redis_key, 0, 0, withscores=True)

        retry_after = 0
        if oldest_entries:
            oldest_timestamp = oldest_entries[0][1]

            expiration_time = oldest_timestamp + RATE_LIMIT_WINDOW_SECONDS
            seconds_left = expiration_time - now
            retry_after = max(0, round(seconds_left, 1))
    except Exception as error:
        print(f" Redis error during cleanup: {error}")

    return {
        "allowed": False,
        "current_count": current_request_count,
        "max_requests": RATE_LIMIT_MAX_REQUESTS,
        "retry_after": retry_after,
    }
