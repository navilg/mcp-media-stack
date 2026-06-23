from fastmcp import FastMCP
import os
import ssl
import requests
import argparse
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

mcp = FastMCP(name="Media Stack MCP")

TRAKT_API_BASE = "https://api.trakt.tv"


def _to_tsv(records: list[dict]) -> str:
    """Convert a list of dicts to TSV (tab-separated values) string.
    First line is column headers, subsequent lines are values.
    """
    if not records:
        return "Empty list"

    headers = list(records[0].keys())

    def _format_val(v):
        if v is None:
            return ""
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        # Escape tabs and newlines to prevent broken TSV rows
        return str(v).replace("\t", "\\t").replace("\n", "\\n")

    lines = ["\t".join(headers)]
    for rec in records:
        lines.append("\t".join(_format_val(rec.get(h, "")) for h in headers))

    return "\n".join(lines)


@mcp.tool
def check_trakt_profile_privacy(username: str | None = None) -> str:
    """
    Check whether a Trakt user's profile is public or private.
    """

    username = username or os.getenv("TRAKT_USERNAME")

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"
    if not username or not username.strip():
        return "Error: username must not be empty"

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
        return f"Error: Failed to check Trakt profile: {exc}"

    if profile_response.status_code == 404:
        return f"Trakt user {username} not found"

    if profile_response.ok:
        data = profile_response.json()
        is_private = data.get("private")
        if isinstance(is_private, bool):
            details = ""
            if is_private:
                details = "Make profile/history public in Trakt privacy settings to allow public access."

            return f"Trakt user {username}'s profile visibility is {"private" if is_private else "public"}. {details}"

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
        return f"Error: Failed to infer profile visibility from history endpoint: {exc}"

    if history_response.status_code == 200:
        return f"Trakt user {username}'s profile visibility is public."

    if history_response.status_code in (401, 403):
        return f"Trakt user {username}'s profile visibility is private. Make profile/history public in Trakt privacy settings to allow public access."

    return  f"Error: Unexpected error. Status code: {history_response.status_code}"


@mcp.tool
def get_trakt_public_watched_movies(username: str | None = None, days: int = 30) -> str:
    """
    Get movies watched in the last N days from a public Trakt profile.
    """

    username = username or os.getenv("TRAKT_USERNAME")

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"
    if not username or not username.strip():
        return "Error: username must not be empty"
    if days <= 0:
        return "Error: days must be greater than 0"

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
        return f"Error: Failed to fetch public watched movies from Trakt: {exc}"

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
                "language": movie.get("language"),
            }
        )

    return _to_tsv(watched_movies)


@mcp.tool
def get_trakt_public_liked_movies(username: str | None = None, threshold_user_rating: int = 7, limit: int = 50) -> str:
    """
    Get liked movies from a public Trakt profile.
    """

    username = username or os.getenv("TRAKT_USERNAME")

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(r) for r in range(threshold_user_rating, 11))  # Filter ratings greater than or equal to threshold

    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"

    params = {
        "limit": str(limit),
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
        return f"Error: Failed to fetch public liked movies from Trakt: {exc}"

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
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(liked_movies)


@mcp.tool
def get_trakt_latest_high_rated_movies(days: int = 30, threshold_rating: float = 7, limit: int = 50) -> str:
    """
    Get recently released high-rated movies from Trakt.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")

    endpoint = f"{TRAKT_API_BASE}/calendars/all/movies/{start_at}/{days}"
    params = {
        "extended": "full",
        "ratings": f"{int(threshold_rating * 10)}-100",  # Filter movies with rating greater than or equal to threshold
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
        return f"Error: Failed to fetch latest movies from Trakt: {exc}"

    movies_data = response.json()
    latest_movies: list[dict] = []
    movies_data = movies_data[:limit]  # Limit the number of movies to process
    for item in movies_data:
        movie = item.get("movie", {})
        latest_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "average_rating": round(movie.get("rating"), 2) if isinstance(movie.get("rating"), (int, float)) else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(latest_movies)


@mcp.tool
def get_trakt_popular_movies(limit: int = 50) -> str:
    """
    Get popular movies from Trakt.
    """

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"

    endpoint = f"{TRAKT_API_BASE}/movies/popular"
    params = {
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
        return f"Error: Failed to fetch popular movies from Trakt: {exc}"

    movies_data = response.json()
    popular_movies: list[dict] = []
    movies_data = movies_data[:limit]  # Limit the number of movies to process
    for movie in movies_data:
        popular_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "average_rating": round(movie.get("rating"), 2) if isinstance(movie.get("rating"), (int, float)) else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(popular_movies)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--transport", type=str, default="streamable-http", help="Transport protocol to use (default: streamable-http)")
    args = parser.parse_args()

    mcp.run(transport=args.transport, host=args.host, port=args.port)