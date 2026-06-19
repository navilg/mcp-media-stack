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
4. Complete OAuth and obtain a Refresh Token.
5. Copy your Client Secret from the Trakt app settings.


### Generate refresh token (device flow)

1. Generate a device code and user code. Copy device code and User code from json response.

~~~bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"client_id": "CLIENT ID"}' \
  https://api.trakt.tv/oauth/device/code
~~~

2. Open this URL in your browser and authenticate using the returned `user_code`:

https://trakt.tv/activate/<USER CODE>

3. Exchange the returned `device_code` for initial tokens (includes refresh token):

~~~bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"client_id": "CLIENT ID", "client_secret": "CLIENT SECRET", "code": "DEVICE CODE"}' \
  https://api.trakt.tv/oauth/device/token
~~~

4. Save `refresh_token` from the response as `TRAKT_REFRESH_TOKEN`.

## Environment variables

Required for all Trakt tools:

- `TRAKT_CLIENT_ID`

Required to auto-generate an access token in `get_trakt_watched_movies`:

- `TRAKT_REFRESH_TOKEN`
- `TRAKT_CLIENT_SECRET`

Optional:

- Pass `access_token` directly to `get_trakt_watched_movies` to bypass refresh-token flow. Access toke expires in 7 days. You will have to regenerate access token if access_token is passed directly.

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
  -e TRAKT_CLIENT_SECRET=your_trakt_client_secret \
  -e TRAKT_REFRESH_TOKEN=your_trakt_refresh_token \
  --name mcp-media-stack \
  mcp-media-stack:latest
~~~

Use this with tool `get_trakt_watched_movies`.

## Run with env file (recommended)

Create a `.env` file:

~~~env
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_CLIENT_SECRET=your_trakt_client_secret
TRAKT_REFRESH_TOKEN=your_trakt_refresh_token
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
- By default, the server refreshes access using `TRAKT_REFRESH_TOKEN`, `TRAKT_CLIENT_ID`, and `TRAKT_CLIENT_SECRET`.
- You can still pass `access_token` directly when calling the tool.
