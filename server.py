from fastmcp import FastMCP
import os
import requests
import argparse
from datetime import datetime, timedelta, timezone

mcp = FastMCP(name="Media Stack MCP")

TRAKT_API_BASE = "https://api.trakt.tv"


@mcp.tool
def check_trakt_profile_privacy(username: str) -> dict:
    """
    Check whether a Trakt user's profile is public or private.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return {"error": "TRAKT_CLIENT_ID is not set"}
    if not username.strip():
        return {"error": "username must not be empty"}

    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
    }

    profile_url = f"{TRAKT_API_BASE}/users/{username}"
    try:
        profile_response = requests.get(
            profile_url,
            params={"extended": "full"},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"error": f"Failed to check Trakt profile: {exc}"}

    if profile_response.status_code == 404:
        return {
            "username": username,
            "exists": False,
            "profile_visibility": "unknown",
            "reason": "User not found",
        }

    if profile_response.ok:
        data = profile_response.json()
        is_private = data.get("private")
        if isinstance(is_private, bool):
            result = {
                "username": username,
                "exists": True,
                "profile_visibility": "private" if is_private else "public",
                "is_private": is_private,
            }
            if is_private:
                result["message"] = "Your Trakt profile is private. Make your profile/history public in Trakt privacy settings to allow public access."
            return result

    # Fallback when private flag is unavailable: infer from public history endpoint.
    history_url = f"{TRAKT_API_BASE}/users/{username}/history/movies"
    try:
        history_response = requests.get(
            history_url,
            params={"limit": "1"},
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return {"error": f"Failed to infer profile visibility from history endpoint: {exc}"}

    if history_response.status_code == 200:
        return {
            "username": username,
            "exists": True,
            "profile_visibility": "public",
            "is_private": False,
            "inference": "Public history endpoint is accessible.",
        }

    if history_response.status_code in (401, 403):
        return {
            "username": username,
            "exists": True,
            "profile_visibility": "private",
            "is_private": True,
            "inference": "Public history endpoint is restricted.",
            "message": "Your Trakt profile is private. Make your profile/history public in Trakt privacy settings to allow public access.",
        }

    return {
        "username": username,
        "exists": True,
        "profile_visibility": "unknown",
        "reason": f"Unexpected status code: {history_response.status_code}",
    }

@mcp.tool
def get_trakt_public_watched_movies(username: str, days: int = 30) -> list[dict]:
    """
    Get movies watched in the last N days from a public Trakt profile.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return [{"error": "TRAKT_CLIENT_ID is not set"}]
    if not username.strip():
        return [{"error": "username must not be empty"}]
    if days <= 0:
        return [{"error": "days must be greater than 0"}]

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    end_at = now_utc.isoformat().replace("+00:00", "Z")

    endpoint = f"{TRAKT_API_BASE}/users/{username}/history/movies"
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
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": f"Failed to fetch public watched movies from Trakt: {exc}"}]

    history_items = response.json()
    watched_movies: list[dict] = []
    for item in history_items:
        movie = item.get("movie", {})
        watched_movies.append(
            {
                "watched_at": item.get("watched_at"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "rating": movie.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language")
            }
        )

    return watched_movies

@mcp.tool
def get_trakt_public_liked_movies(username: str, threshold_user_rating: int = 7, limit: int = 50) -> list[dict]:
    """
    Get liked movies from a public Trakt profile.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return [{"error": "TRAKT_CLIENT_ID is not set"}]
    if not username.strip():
        return [{"error": "username must not be empty"}]
    
    rating = ",".join(str(r) for r in range(threshold_user_rating, 11))  # Filter ratings greater than or equal to threshold

    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"

    params = {
        "limit": str(limit),
        "extended": "full"
    }
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": f"Failed to fetch public liked movies from Trakt: {exc}"}]

    liked_items = response.json()
    liked_movies: list[dict] = []
    for item in liked_items:
        movie = item.get("movie", {})
        liked_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview")            }
        )

    return liked_movies

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--transport", type=str, default="streamable-http", help="Transport protocol to use (default: streamable-http)")
    args = parser.parse_args()

    mcp.run(transport=args.transport, host=args.host, port=args.port)