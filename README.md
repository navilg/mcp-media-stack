# MCP Media Stack

FastMCP server that exposes Trakt tools for public profile checks and public watched-movie history.

## What this server provides

- `check_trakt_profile_privacy(username)`
- `get_trakt_public_watched_movies(username, days=30)`

## Prerequisites

- Docker installed on your machine
- A Trakt application (to get a Client ID)

## Trakt setup

1. Create or log in to your Trakt account.
2. Create an API app in Trakt settings.
3. Copy your Client ID.

## Environment variables

Required for all Trakt tools:

- `TRAKT_CLIENT_ID`

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
  --name mcp-media-stack \
  mcp-media-stack:latest
~~~

Use this with tools `check_trakt_profile_privacy` and `get_trakt_public_watched_movies`.

## Run with env file (recommended)

Create a `.env` file:

~~~env
TRAKT_CLIENT_ID=your_trakt_client_id
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

`get_trakt_public_watched_movies` returns a list of watched movies with these fields:

- `watched_at`
- `title`
- `year`
- `rating_by_user`
- `average_rating`
- `genre`

`check_trakt_profile_privacy` returns profile status fields such as:

- `username`
- `exists`
- `profile_visibility`
- `is_private`
- `message` (included when profile is private)

## Notes

- Default watched window is 30 days (`days=30`).
- Public watched history is read via `/users/{username}/history/movies`.
- If a profile is private, `check_trakt_profile_privacy` returns a message to make profile/history public in Trakt privacy settings.
