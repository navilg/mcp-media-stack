# MCP Media Stack

FastMCP server that exposes movie-related tools backed by Trakt and TMDb APIs.

## Tools

The server currently exposes these MCP tools:

- `check_trakt_profile_privacy(username=None)`
- `get_trakt_public_watched_movies(username=None, days=30)`
- `get_trakt_public_liked_movies(username=None, threshold_user_rating=7, limit=50)`
- `get_tmdb_latest_high_rated_movies(limit=50, num_days=30, threshold_rating=7, threshold_vote_count=500, language="en-US")`
- `get_tmdb_popular_movies(limit=50, language="en-US")`

## Prerequisites

- Python 3.11+ (for local run) or Docker (for container run)
- Trakt API client ID for Trakt tools
- TMDb bearer token for TMDb tools

## Environment variables

Set the following as needed by the tools you call.

### Trakt

- `TRAKT_CLIENT_ID` (required for Trakt tools)
- `TRAKT_USERNAME` (optional default username if `username` tool argument is omitted)

### TMDb

- `TMDB_BEARER_TOKEN` (required for TMDb tools)

## Quick start (Docker)

Build image:

```bash
docker build -t mcp-media-stack:latest .
```

Run container (port 8000):

```bash
docker run --rm -p 8000:8000 \
  -e TRAKT_CLIENT_ID=your_trakt_client_id \
  -e TRAKT_USERNAME=your_trakt_username \
  -e TMDB_BEARER_TOKEN=your_tmdb_bearer_token \
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Quick start (.env file)

Create `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_USERNAME=your_trakt_username
TMDB_BEARER_TOKEN=your_tmdb_bearer_token
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
python server.py --host 0.0.0.0 --port 8000 --transport streamable-http
```

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
- TMDb tools return condensed movie metadata (title, release date, ratings, genre IDs, overview).
