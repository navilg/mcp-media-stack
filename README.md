# MCP Media Stack

FastMCP server that exposes Trakt tools to fetch movies watched in the last N days.

## What this server provides

- `get_trakt_watched_movies(days=30, access_token=None)`

## Prerequisites

- Docker installed on your machine
- A Trakt application (to get a Client ID)

## Trakt setup

1. Create or log in to your Trakt account.
2. Create an API app in Trakt settings.
3. Copy your Client ID.
4. Complete OAuth and obtain an Access Token.

OAuth reference:
https://trakt.docs.apiary.io/#reference/authentication-oauth

## Environment variables

Required for all Trakt tools:

- `TRAKT_CLIENT_ID`

Required for the watched movies tool (if not passed as function argument):

- `TRAKT_ACCESS_TOKEN`

## Build container image

From this project directory, run:

~~~bash
docker build -t mcp-media-stack:latest .
~~~

## Run container

The server listens on port `8000` by default.

### Run with Trakt access

~~~bash
docker run --rm -p 8000:8000 \
  -e TRAKT_CLIENT_ID=your_trakt_client_id \
  -e TRAKT_ACCESS_TOKEN=your_trakt_access_token \
  --name mcp-media-stack \
  mcp-media-stack:latest
~~~

Use this with tool `get_trakt_watched_movies`.

## Run with env file (recommended)

Create a `.env` file:

~~~env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_ACCESS_TOKEN=your_trakt_access_token
~~~

Then run:

~~~bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --name mcp-media-stack \
  mcp-media-stack:latest
~~~

## Verify container is running

- Check logs:

~~~bash
docker logs -f mcp-media-stack
~~~

- Check running containers:

~~~bash
docker ps
~~~

## Stop container

~~~bash
docker stop mcp-media-stack
~~~

## Local run without Docker (optional)

~~~bash
pip install -r requirements.txt
python server.py --host 0.0.0.0 --port 8000 --transport streamable-http
~~~

## Tool response

`get_trakt_watched_movies` returns a list of watched movies with these fields:

- `watched_at`
- `title`
- `year`
- `rating_by_user`
- `average_rating`
- `genre`

## Notes

- Default watched window is 30 days (`days=30`).
- The server currently reads the authenticated user's Trakt watch history via `/users/me/history/movies`.
- A valid OAuth access token is required unless you pass `access_token` directly to the tool.
