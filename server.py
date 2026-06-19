from fastmcp import FastMCP
import os
import requests
import argparse
from datetime import datetime, timedelta, timezone

mcp = FastMCP(name="Media Stack MCP")

TRAKT_API_BASE = "https://api.trakt.tv"

def get_access_token() -> str | None:
    """
    Generate refresh token from access token. This is needed because the access token expires after 7 days, while the refresh token can be used to get a new access token without user intervention.
    """

    refresh_token = os.getenv("TRAKT_REFRESH_TOKEN")
    if not refresh_token:
        print("TRAKT_REFRESH_TOKEN is not set. Cannot refresh access token.")
        return None
    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    trakt_client_secret = os.getenv("TRAKT_CLIENT_SECRET")
    if not trakt_client_id or not trakt_client_secret:
        print("TRAKT_CLIENT_ID and TRAKT_CLIENT_SECRET must be set to refresh access token.")
        return None
    
    token_url = f"{TRAKT_API_BASE}/oauth/token"
    payload = {
        "refresh_token": refresh_token,
        "client_id": trakt_client_id,
        "client_secret": trakt_client_secret,
        "redirect_uri": "https://localhost:8000",
        "grant_type": "refresh_token",
    }

    try:
        response = requests.post(token_url, json=payload, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to refresh access token: {exc}")
        return None
    
    token_data = response.json()
    new_access_token = token_data.get("access_token")
    if not new_access_token:
        print("Failed to get new access token from response.")
        return None

    return new_access_token

@mcp.tool
def get_trakt_watched_movies(days: int = 30, access_token: str | None = None) -> list[dict]:
    """
    Get movies watched in the last N days from a Trakt profile.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return [{"error": "TRAKT_CLIENT_ID is not set"}]
    if days <= 0:
        return [{"error": "days must be greater than 0"}]

    token = access_token or get_access_token()
    if not token:
        return [{"error": "No access token provided/generated. Pass access_token or set TRAKT_REFRESH_TOKEN."}]

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    end_at = now_utc.isoformat().replace("+00:00", "Z")

    endpoint = f"{TRAKT_API_BASE}/users/me/history/movies"
    params = {
        "start_at": start_at,
        "end_at": end_at,
        "limit": "1000",
        "extended": "full",
    }
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
        "Authorization": f"Bearer {token}",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": f"Failed to fetch private watched movies from Trakt: {exc}"}]

    history_items = response.json()
    watched_movies: list[dict] = []
    for item in history_items:
        movie = item.get("movie", {})
        watched_movies.append(
            {
                "watched_at": item.get("watched_at"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "rating_by_user": item.get("rating"),
                "average_rating": movie.get("rating"),
                "genre": movie.get("genres", []),
            }
        )

    return watched_movies
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--transport", type=str, default="streamable-http", help="Transport protocol to use (default: streamable-http)")
    args = parser.parse_args()

    mcp.run(transport=args.transport, host=args.host, port=args.port)