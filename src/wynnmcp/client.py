"""Async HTTP client with bounded caching and retries for read-only API calls."""

import asyncio
import copy
import json
import re
import time
from collections import OrderedDict
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

BASE_URL = "https://api.wynncraft.com/v3"
HEADERS = (
    "cache-control",
    "cache-source",
    "ratelimit-remaining",
    "ratelimit-reset",
    "ratelimit-limit",
    "ratelimit-bucket",
    "version",
    "retry-after",
)


class WynnAPIError(Exception):
    def __init__(self, payload: dict):
        self.payload = payload
        super().__init__(payload.get("error", "Wynncraft API error"))


def retry_delay(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("retry-after", response.headers.get("ratelimit-reset"))
    if value is not None:
        try:
            return max(0, float(value))
        except ValueError:
            try:
                return max(0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return float(2**attempt)


class WynnClient:
    def __init__(self, token: str | None = None, *, transport=None):
        headers = {"User-Agent": "WynnMCP/0.1.0", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = httpx.AsyncClient(
            headers=headers,
            timeout=20,
            follow_redirects=False,
            transport=transport,
        )
        self.cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self.lock = asyncio.Lock()

    async def close(self):
        await self.http.aclose()

    async def request(self, method: str, path: str, query: str = "", body=None) -> dict:
        url = BASE_URL + path + ("?" + query if query else "")
        key = json.dumps([method, url, body], sort_keys=True)
        # Serialize requests so simultaneous tool calls cannot burst the upstream API.
        async with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > time.monotonic():
                self.cache.move_to_end(key)
                result = copy.deepcopy(cached[1])
                result["cached"] = True
                return result
            for attempt in range(3):
                try:
                    response = await self.http.request(method, url, json=body)
                except httpx.RequestError:
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise WynnAPIError(
                        {
                            "error": "NetworkError",
                            "detail": "Could not reach Wynncraft after 3 attempts.",
                        }
                    ) from None
                if response.status_code == 429 or response.status_code >= 500:
                    delay = retry_delay(response, attempt)
                    # Surface long rate limits immediately rather than violating Retry-After.
                    if attempt < 2 and delay <= 5:
                        await asyncio.sleep(delay)
                        continue
                break
            metadata = {h: response.headers[h] for h in HEADERS if h in response.headers}
            try:
                data = response.json()
            except ValueError:
                raise WynnAPIError(
                    {
                        "error": "InvalidResponse",
                        "status": response.status_code,
                        "detail": "Wynncraft returned a non-JSON response.",
                    }
                ) from None
            result = {
                "status": response.status_code,
                "data": data,
                "headers": metadata,
                "cached": False,
            }
            # Preserve multiple-match candidates so the caller can choose a UUID.
            if response.status_code == 300:
                return result
            if not response.is_success:
                raise WynnAPIError({"error": "WynncraftAPIError", **result})
            control = response.headers.get("cache-control", "").lower()
            match = re.search(r"(?:^|[,\s])max-age=(\d+)", control)
            if match and "no-store" not in control and "no-cache" not in control:
                try:
                    age = max(0, int(response.headers.get("age", "0")))
                except ValueError:
                    age = 0
                ttl = min(300, max(0, int(match[1]) - age))
                if ttl and len(response.content) <= 1_000_000:
                    self.cache[key] = (time.monotonic() + ttl, copy.deepcopy(result))
                    self.cache.move_to_end(key)
                    while len(self.cache) > 32:
                        self.cache.popitem(last=False)
            return result
