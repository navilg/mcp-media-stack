# MCP Media Stack

FastMCP server that exposes movie-related tools backed by Trakt API.

## Tools

The server currently exposes these MCP tools:

- `check_trakt_profile_privacy(username=None)`
- `get_trakt_public_watched_movies(username=None, days=30)`
- `get_trakt_public_liked_movies(username=None, threshold_user_rating=7, limit=50)`
- `get_trakt_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_trakt_popular_movies(limit=50)`

## Prerequisites

- Python 3.11+ (for local run) or Docker (for container run)
- Trakt API client ID

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TRAKT_CLIENT_ID` | Yes | Trakt API client ID |
| `TRAKT_USERNAME` | No | Optional default username if `username` tool argument is omitted |
| `MCP_BEARER_TOKEN` | No | Bearer token for MCP server authentication (see [Authentication](#authentication) below) |

## Authentication

When `MCP_BEARER_TOKEN` is set, the MCP server requires Bearer token authentication for all **HTTP-based transports** (`streamable-http`, `sse`).

- **STDIO transport** is unaffected — MCP authentication applies only to HTTP transports.
- **If `MCP_BEARER_TOKEN` is omitted or unset**, authentication is disabled and the server runs openly.

### Clients must send the Authorization header

```http
Authorization: Bearer <MCP_BEARER_TOKEN>
```

### Example: FastMCP client with Bearer token

```python
from fastmcp import Client

async with Client(
    "http://your-server:8000/mcp",
    auth="your_mcp_bearer_token",
) as client:
    await client.ping()
```

### Example: StreamableHttpTransport with Bearer token

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport(
    "http://your-server:8000/mcp",
    auth="your_mcp_bearer_token",
)

async with Client(transport) as client:
    await client.ping()
```

## Quick start (Docker)

Build image:

```bash
docker build -t mcp-media-stack:latest .
```

Run container (port 8000) with Bearer token:

```bash
docker run --rm -p 8000:8000 \
  -e TRAKT_CLIENT_ID=your_trakt_client_id \
  -e TRAKT_USERNAME=your_trakt_username \
  -e MCP_BEARER_TOKEN=your_mcp_bearer_token \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Quick start (.env file)

Create `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_USERNAME=your_trakt_username
MCP_BEARER_TOKEN=your_mcp_bearer_token
```

Run with env file:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Local run (without Docker)

```bash
python -m pip install -r requirements.txt
MCP_BEARER_TOKEN=your_mcp_bearer_token python server.py --host 0.0.0.0 --port 8000 --transport streamable-http
```

Or set via environment variable:

```bash
export MCP_BEARER_TOKEN=your_mcp_bearer_token
python server.py --host 0.0.0.0 --port 8000 --transport streamable-http
```

## Test script (using test.env)

A test script is included to validate tool functionality against the Python functions in `server.py`.

- Create your test env file:

```bash
cp test.env.example test.env
```

- Fill in credentials and test inputs in `test.env`.

- Run tests:

```bash
python test_server.py
```

The script automatically loads `test.env` and runs all test functions sequentially, printing results for each tool call.

## Operational commands

View logs:

```bash
docker logs -f mcp-media-stack
```

List running containers:

```bash
docker ps
```

Stop container:

```bash
docker stop mcp-media-stack
```

## Notes

- Default server bind is `0.0.0.0:8000`.
- Trakt tools support passing `username` directly or using `TRAKT_USERNAME` as fallback.
- `get_trakt_public_watched_movies` defaults to the last 30 days.
- Trakt tools return condensed movie metadata including title, release date, ratings, genres, and certification.
- Bearer token authentication uses FastMCP's `StaticTokenVerifier` — suitable for service accounts, CI/CD, and pre-shared tokens. For production, consider migrating to JWT or OAuth verification.