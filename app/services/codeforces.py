from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import httpx

from app.core.config import settings


class CodeforcesAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, cf_comment: str | None = None):
        self.status_code = status_code
        self.cf_comment = cf_comment
        super().__init__(message)


class RateLimiter:
    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


class CodeforcesClient:
    BASE_URL = settings.cf_api_base_url
    TIMEOUT = settings.request_timeout
    MAX_RETRIES = settings.max_retries

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(settings.rate_limit_per_second)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self.TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        client = await self._get_client()
        await self._rate_limiter.acquire()

        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.request(method, endpoint, **kwargs)
                data = response.json()

                if response.status_code != 200 or data.get("status") != "OK":
                    comment = data.get("comment", "Unknown error")
                    if response.status_code == 503 and attempt < self.MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    raise CodeforcesAPIError(
                        f"CF API error: {comment}",
                        status_code=response.status_code,
                        cf_comment=comment,
                    )

                return cast(dict[str, Any], data["result"])

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 503 and attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                else:
                    raise CodeforcesAPIError(
                        f"HTTP {e.response.status_code}",
                        status_code=e.response.status_code,
                    ) from e
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** (attempt + 1))

        raise CodeforcesAPIError(f"Max retries exceeded: {last_error}") from last_error

    async def fetch_user_profile(self, handle: str) -> dict[str, Any] | None:
        result = await self._request("GET", "/user.info", params={"handles": handle})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

    async def fetch_rating_history(self, handle: str) -> list[dict[str, Any]]:
        result = await self._request("GET", "/user.rating", params={"handle": handle})
        return result if isinstance(result, list) else []

    async def fetch_submissions(
        self, handle: str, count: int = 1000, offset: int = 1
    ) -> list[dict[str, Any]]:
        result = await self._request(
            "GET",
            "/user.status",
            params={"handle": handle, "from": offset, "count": count},
        )
        return result if isinstance(result, list) else []

    async def fetch_all_submissions(self, handle: str) -> list[dict[str, Any]]:
        all_subs: list[dict[str, Any]] = []
        offset = 1
        batch_size = 1000
        while True:
            batch = await self.fetch_submissions(handle, count=batch_size, offset=offset)
            if not batch:
                break
            all_subs.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return all_subs

    async def fetch_contest_list(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/contest.list", params={"gym": "false"})
        return result if isinstance(result, list) else []

    async def fetch_problems(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/problemset.problems")
        if isinstance(result, dict):
            return cast(list[dict[str, Any]], result.get("problems", []))
        return []

    async def fetch_user_rated_contests(self, handle: str) -> list[dict[str, Any]]:
        return await self.fetch_rating_history(handle)

    async def get_cached_contest_list(self) -> list[dict[str, Any]]:
        from app.services.cache import cached

        @cached("contest_list", file_ttl=86400, mem_ttl=3600)
        async def _fetch() -> list[dict[str, Any]]:
            return await self.fetch_contest_list()

        return await _fetch()

    async def get_cached_problems(self) -> list[dict[str, Any]]:
        from app.services.cache import cached

        @cached("problemset", file_ttl=86400, mem_ttl=3600)
        async def _fetch() -> list[dict[str, Any]]:
            return await self.fetch_problems()

        return await _fetch()


async def get_cf_client() -> CodeforcesClient:
    return CodeforcesClient()
