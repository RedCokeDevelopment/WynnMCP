# WynnMCP

A Python MCP server for the [Wynncraft v3 API](https://docs.wynncraft.com/welcome).
Runs locally over stdio and provides 40 read-only tools derived from the official
OpenAPI specification (snapshot: October 8, 2026). No API token is required for public data.

## AstrBot: install and connect

WynnMCP installs as a normal Python package. No repository path is needed in
AstrBot's configuration. Python 3.11 or newer is required.

### Install from GitHub

Once the code is pushed to the public repository, run this in the environment
where AstrBot launches its MCP processes (Git must be installed):

```sh
python -m pip install "git+https://github.com/RedCokeDevelopment/WynnMCP.git"
python -m wynnmcp --version
```

Use the same Python interpreter for installation and the MCP command below.
If AstrBot runs in Docker, install inside its container or build the package
into a custom image; installing on the host does not install it in the container.
Manual container installs are lost when the container is recreated.

### Configure AstrBot

In **Plugins → MCP → Add MCP server**, enter `WynnMCP` as the server name,
choose the **Stdio** template, and paste this into the server configuration:

```json
{
  "command": "python",
  "args": ["-m", "wynnmcp"]
}
```

This dialog takes one server configuration: do not wrap it in `mcpServers`.
Click **Test connection**, then **Save**. AstrBot starts the server automatically.
If `python` resolves to a different environment, use the installed interpreter's
absolute path in `command`. If your environment calls it `python3`, use `python3`
in both the installation command and this configuration.

Try asking “Look up the Wynncraft player Salted” or “Find items named Cascade.”
Public data does not need a token. For authenticated access, add an `env` object
to the same configuration with `WYNNCRAFT_API_TOKEN` set to your token.

### Alternative: let uv install and launch it

If `uv` and Git are available, this configuration installs WynnMCP
in an isolated environment on first launch without a separate pip command:

```json
{
  "command": "uv",
  "args": [
    "tool", "run",
    "--from", "git+https://github.com/RedCokeDevelopment/WynnMCP.git",
    "wynnmcp"
  ]
}
```

For a fixed version, append an existing release tag or commit hash to the Git
URL, such as `.git@v0.1.0` after that tag has been published.

### Install a release wheel (no Git required)

Download the `.whl` file from [GitHub Releases](https://github.com/RedCokeDevelopment/WynnMCP/releases)
once a release is available, then install it in AstrBot's Python environment:

```sh
python -m pip install ./wynnmcp-0.1.0-py3-none-any.whl
```

Use the downloaded filename if the version differs. Keep the same AstrBot
`python -m wynnmcp` configuration. You can also give pip the wheel's direct
download URL from the release. Python dependencies are installed automatically.

## Connect other MCP clients from a local checkout

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and clone
or download this repository. WynnMCP requires Python 3.11 or newer; uv can
automatically download a compatible Python version if needed.

Add the following entry to your MCP client's configuration. If your configuration
already has an `mcpServers` object, add `WynnMCP` inside it.

Replace `<absolute-path-to-wynnMCP>` with the **full path to the repository
folder containing `pyproject.toml`**.

```json
{
  "mcpServers": {
    "WynnMCP": {
      "command": "uv",
      "args": [
        "--directory",
        "<absolute-path-to-wynnMCP>",
        "run",
        "--locked",
        "wynnmcp"
      ]
    }
  }
}
```

Example repository paths in JSON:

- **Windows:** `"C:\\path\\to\\wynnMCP"` or `"C:/path/to/wynnMCP"`
- **macOS:** `"/Users/yourname/projects/wynnMCP"`
- **Linux:** `"/home/yourname/projects/wynnMCP"`

Restart your MCP client or reload its server configuration. The client launches
WynnMCP automatically, and uv installs the required dependencies on the first run.
You do not need to start the server separately.

If the client reports that `uv` cannot be found, replace `"uv"` in `command`
with its full executable path. Find that path using `(Get-Command uv).Source`
in PowerShell or `command -v uv` on macOS/Linux.

Once connected, try asking:

- “Look up the Wynncraft player Salted.”
- “Find items named Cascade.”
- “Show me the Mage ability tree.”

Public data works without an API token. See [Authentication](#authentication)
for authenticated access.

## Run manually

For development or troubleshooting, open a terminal in the repository folder:

```sh
uv sync
uv run --locked wynnmcp
```

The process waits for an MCP client on stdin. It is not an interactive terminal
application or a web server. All diagnostics go to stderr.

Alternatively: `python -m pip install .`, then `python -m wynnmcp`.

## Authentication

For authenticated limits and permitted private data, set `WYNNCRAFT_API_TOKEN`
in the environment inherited by the server. It accepts a Wynncraft account token
or an existing OAuth2 access token, sent as `Authorization: Bearer ...`.
An `.env` file is not loaded automatically. Never paste tokens into tool arguments.
Create account tokens at <https://wynncraft.com/account/dashboard?section=dev>.
Use a public-mode token if sharing the server. Token exchange and refresh are outside
this server's scope. `get_player_identity` requires a suitable authenticated token;
`get_oauth_identity` requires an OAuth2 access token.

## Tools

| Area               | Tools                                                                                                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Players            | `list_online_players`, `get_player_identity`, `get_player`, `list_player_characters`, `get_player_character`, `get_player_character_abilities`                         |
| OAuth identity     | `get_oauth_identity`                                                                                                                                                   |
| Guilds             | `list_guilds`, `list_guild_territories`, `list_guild_seasons`, `get_guild_by_prefix`, `get_guild_by_uuid`, `get_guild_by_name`                                         |
| Items and crafting | `list_items`, `search_items`, `quick_search_items`, `list_recipes`, `search_recipes`, `get_item_metadata`, `list_item_sets`                                            |
| Classes            | `get_ability_tree`, `get_ability_map`, `list_aspects`, `list_classes`, `get_class`                                                                                     |
| Map                | `list_map_markers`, `list_player_locations`, `list_world_events`, `list_map_camps`, `list_map_raids`, `list_map_loot_pools`, `list_gathering_nodes`, `get_quest_count` |
| Search             | `global_search`                                                                                                                                                        |
| Leaderboards       | `list_leaderboard_types`, `get_leaderboard`                                                                                                                            |
| News               | `fetch_publisher_article`, `list_publisher_articles`, `list_publisher_videos`, `list_latest_news`                                                                      |

Examples of tool arguments:

```json
{"tool": "get_player", "arguments": {"username": "Salted", "fullResult": true}}
{"tool": "search_items", "arguments": {"filters": {"query": "Cascade"}, "page": 1}}
{"tool": "get_guild_by_prefix", "arguments": {"query": "Nia"}}
{"tool": "get_ability_tree", "arguments": {"tree": "mage"}}
{"tool": "get_leaderboard", "arguments": {"lb_type": "playerContent", "resultLimit": 10}}
```

Parameter names follow the API, including `fullResult` for items/players and
`full_result` for recipes. These and `static` are boolean tool inputs: true
sends a bare query flag; false omits it. Pages start at 1. Full-result flags can
return very large payloads; prefer pagination. Search POSTs only read data.

Results contain `status`, the unchanged JSON `data`, selected cache/rate-limit
`headers`, and a local `cached` flag. HTTP 300 is returned with all selection
candidates; retry with the desired UUID. API failures are MCP tool errors, preserving
the upstream JSON. Player privacy restrictions remain authoritative; hidden stats
must not be interpreted as zero. HTML/markup and news text are external data.

Requests have a 20-second HTTP timeout and at most three attempts for network errors,
429s, and 5xx responses. Retry-After and RateLimit-Reset delays up to five seconds
are honored automatically; longer waits are returned to the caller. Requests are
serialized, but there is no proactive per-bucket rate limiter. Cache entries respect
max-age and Age, capped at five minutes, 32 entries and 1 MB per response. Caches
are isolated to each process/token and cleared when the server exits. Cached
rate-limit headers describe the original request. Redirects are not followed.

## Development

```powershell
uv sync --group dev
uv run pytest
uv run ruff check .
uv build
```

`uv build` creates an installable wheel and source archive in `dist/`.
The GitHub Actions release workflow tests and builds the project when a GitHub
Release is published, then attaches both files to that release. Set the release
tag to `v` followed by the package version (for example `v0.1.0`); the workflow
checks that it matches `pyproject.toml`. It does not publish to PyPI.

Tests use mock HTTP responses plus an actual stdio MCP subprocess. No token or
network connection is needed for the test suite.

The checked-in `src/wynnmcp/endpoints.json` provides tool schemas without fetching
documentation at startup. Refresh it using `uv run python scripts/update_catalog.py`.
If the documentation CDN blocks Python requests, download the specification first:

```powershell
New-Item -ItemType Directory -Force work | Out-Null
Invoke-WebRequest https://docs.wynncraft.com/openapi.json -OutFile work/openapi.json
uv run python scripts/update_catalog.py --spec work/openapi.json
```

Review schema changes and run tests after refreshing. The catalog exposes all
documented GET endpoints and the two read-only search POSTs; it intentionally
excludes `/oauth/token`. Enum values reflect the snapshot and may need refreshing
when Wynncraft adds content. This project is an unofficial integration.

----

Wynncraft Studio (or Wynncraft) does not endorse or in any way affiliate with this project or RED COKE DEVELOPMENT LTD. All trademarks, service marks, and trade names are the property of their respective owners.
