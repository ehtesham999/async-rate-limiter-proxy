import httpx
from fastapi import APIRouter, Request, Response
from app.core.config import TARGET_API_BASE_URL, PROXY_TIMEOUT_SECONDS
from app.services.rate_limiter import check_rate_limit


router = APIRouter()


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_request(full_path: str, request: Request):
    if request.client is not None:
        client_ip = request.client.host
    else:
        client_ip = "unknown"

    rate_limit_result = await check_rate_limit(client_ip)

    if not rate_limit_result["allowed"]:
        return Response(
            content=(
                f'{{"error": "Rate limit exceeded.", "retry_after": {rate_limit_result["retry_after"]}}}'
            ),
            status_code=429,
            media_type="application/json",
            headers={
                "X-RateLimit-Limit": str(rate_limit_result["max_requests"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Retry-After": str(rate_limit_result["retry_after"]),
            },
        )

    target_url = f"{TARGET_API_BASE_URL}/{full_path}"

    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    request_body = await request.body()
    headers_to_forward = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() in {"host", "accept-encoding"}:
            continue
        headers_to_forward[header_name] = header_value

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT_SECONDS) as client:
            response_from_target = await client.request(
                method=request.method,
                url=target_url,
                headers=headers_to_forward,
                content=request_body,
            )

    except httpx.TimeoutException:
        return Response(
            content='{"error": "Target API timed out"}',
            status_code=504,
            media_type="application/json",
        )

    except httpx.RequestError as error:
        return Response(
            content=f'{{"error": "Could not reach target API: {error}"}}',
            status_code=502,
            media_type="application/json",
        )

    headers_to_skip = {"transfer-encoding", "content-encoding", "content-length"}

    response_headers = {}
    for header_name, header_value in response_from_target.headers.items():
        if header_name.lower() in headers_to_skip:
            continue
        response_headers[header_name] = header_value

    final_response = Response(
        content=response_from_target.content,
        status_code=response_from_target.status_code,
        headers=response_headers,
        media_type=response_from_target.headers.get("content-type"),
    )

    remaining = rate_limit_result["max_requests"] - rate_limit_result["current_count"]
    final_response.headers["X-RateLimit-Limit"] = str(rate_limit_result["max_requests"])
    final_response.headers["X-RateLimit-Remaining"] = str(remaining)
    return final_response
