import json
import sys

import httpx
import pytest
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from wynnmcp.client import WynnAPIError, WynnClient, retry_delay
from wynnmcp.server import CATALOG, build_request, create_server


def test_catalog():
    assert len(CATALOG) == 40
    for endpoint in CATALOG.values():
        Draft202012Validator.check_schema(endpoint["schema"])
        assert endpoint["path"] != "/oauth/token"
        assert endpoint["method"] == "GET" or endpoint["path"] in (
            "/item/search",
            "/item/recipe/search",
        )


@pytest.mark.parametrize(
    "tool,flag",
    [
        ("get_player", "fullResult"),
        ("list_items", "fullResult"),
        ("list_recipes", "full_result"),
        ("get_item_metadata", "static"),
    ],
)
def test_presence_flags(tool, flag):
    args = {"username": "Salted"} if tool == "get_player" else {}
    assert build_request(CATALOG[tool], {**args, flag: True})[1] == flag
    assert build_request(CATALOG[tool], {**args, flag: False})[1] == ""


def test_encoding_and_filters():
    path, query, _ = build_request(CATALOG["get_guild_by_name"], {"query": "A / B?x=#"})
    assert path == "/guild/A%20%2F%20B%3Fx%3D%23"
    assert query == ""
    assert build_request(CATALOG["search_items"], {"filters": {"query": "Cascade"}, "page": 2}) == (
        "/item/search",
        "page=2",
        {"query": "Cascade"},
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_player", {}),
        ("get_player", {"username": ".."}),
        ("get_player", {"username": ""}),
        ("list_items", {"page": 0}),
        ("list_items", {"page": True}),
        ("list_items", {"fullResult": "false"}),
        ("get_ability_tree", {"tree": "invalid"}),
        ("get_leaderboard", {"lb_type": "playerContent", "resultLimit": 1001}),
        ("search_items", {"filters": {"unknown": 1}}),
        ("list_classes", {"token": "secret"}),
    ],
)
def test_invalid_arguments(tool, args):
    with pytest.raises(ValueError):
        build_request(CATALOG[tool], args)


async def test_auth_cache_and_query():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.url.query == b"fullResult"
        return httpx.Response(
            200, json={"username": "Salted"}, headers={"Cache-Control": "max-age=60"}
        )

    client = WynnClient("test-token", transport=httpx.MockTransport(handler))
    try:
        first = await client.request("GET", "/player/Salted", "fullResult")
        first["data"]["username"] = "mutated"
        second = await client.request("GET", "/player/Salted", "fullResult")
        assert second["cached"] and second["data"]["username"] == "Salted"
        assert len(requests) == 1
    finally:
        await client.close()


@pytest.mark.parametrize(
    "control,age",
    [("no-store, max-age=60", "0"), ("max-age=60", "60"), ("no-cache, max-age=60", "0")],
)
async def test_uncacheable(control, age):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={}, headers={"Cache-Control": control, "Age": age})

    client = WynnClient(transport=httpx.MockTransport(handler))
    try:
        await client.request("GET", "/classes")
        await client.request("GET", "/classes")
        assert len(calls) == 2
    finally:
        await client.close()


@pytest.mark.parametrize("status", [429, 503])
async def test_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status if len(calls) < 3 else 200, json={}, headers={"Retry-After": "0"}
        )

    client = WynnClient(transport=httpx.MockTransport(handler))
    try:
        assert (await client.request("GET", "/classes"))["status"] == 200
        assert len(calls) == 3
    finally:
        await client.close()


async def test_long_rate_limit_no_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": "RateLimit"}, headers={"Retry-After": "60"})

    client = WynnClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(WynnAPIError) as exc:
            await client.request("GET", "/classes")
        assert exc.value.payload["headers"]["retry-after"] == "60"
        assert len(calls) == 1
    finally:
        await client.close()


def test_retry_date():
    response = httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
    assert retry_delay(response, 0) == 0


async def test_mcp_calls():
    def handler(request):
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, json={"error": "NotFound", "detail": "Player not found"})
        if request.url.path.endswith("/ambiguous"):
            return httpx.Response(300, json={"objects": {"uuid": {"username": "name"}}})
        return httpx.Response(200, json={"mage": {"name": "Mage"}})

    client = WynnClient(transport=httpx.MockTransport(handler))
    try:
        async with create_connected_server_and_client_session(create_server(client)) as session:
            tools = await session.list_tools()
            assert len(tools.tools) == 40
            assert all(tool.annotations.readOnlyHint for tool in tools.tools)
            result = await session.call_tool("list_classes", {})
            assert not result.isError
            assert json.loads(result.content[0].text)["data"]["mage"]["name"] == "Mage"
            missing = await session.call_tool("get_player", {"username": "missing"})
            assert missing.isError
            assert json.loads(missing.content[0].text)["status"] == 404
            ambiguous = await session.call_tool("get_player", {"username": "ambiguous"})
            assert not ambiguous.isError
            assert "objects" in json.loads(ambiguous.content[0].text)["data"]
            invalid = await session.call_tool("get_player", {})
            assert invalid.isError
    finally:
        await client.close()


async def test_stdio_process():
    params = StdioServerParameters(command=sys.executable, args=["-m", "wynnmcp"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "WynnMCP"
        assert len((await session.list_tools()).tools) == 40
        result = await session.call_tool("list_items", {"page": 0})
        assert result.isError


@pytest.mark.parametrize(
    "status,body", [(200, "<html>error</html>"), (302, "{}"), (403, '{"error": "Forbidden"}')]
)
async def test_bad_responses(status, body):
    client = WynnClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, text=body)))
    try:
        with pytest.raises(WynnAPIError):
            await client.request("GET", "/classes")
    finally:
        await client.close()
