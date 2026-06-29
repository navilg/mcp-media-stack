# MCP Media Stack

FastMCP server that exposes movie-related tools backed by Trakt API.

## Tools

The server currently exposes these MCP tools:

- `check_trakt_profile_privacy(username=None)`
- `get_trakt_public_watched_movies(username=None, days=30)`
- `get_trakt_public_liked_movies(username=None, threshold_user_rating=7, limit=50)`
- `get_trakt_latest_high_rated_movies(days=30, threshold_rating=7, limit=50)`
- `get_trakt_popular_movies(limit=50)`
- `get_radarr_movies()`
- `get_radarr_quality_profiles()`
- `get_radarr_root_folders()`
- `add_radarr_movie(movie_query, root_folder_path, quality_profile_id)`
- `delete_radarr_movie(movie_query, delete_files=False)`

## Prerequisites

- Python 3.11+ (for local run) or Docker (for container run)
- Trakt API client ID

## Environment variables

Set the following as needed:

- `TRAKT_CLIENT_ID` (required)
- `TRAKT_USERNAME` (optional default username if `username` tool argument is omitted)
- `RADARR_URL` (required for Radarr tools)
- `RADARR_API_KEY` (required for Radarr tools)

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
  --name mcp-media-stack \
  mcp-media-stack:latest
```

## Quick start (.env file)

Create `.env`:

```env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_USERNAME=your_trakt_username
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
- `add_radarr_movie` looks up the movie by query string, then adds it with monitor set to movie only, minimum availability set to released, and search enabled.
- `delete_radarr_movie` looks up the movie by query string before deleting it; set `delete_files=True` to remove the file from disk as well.
