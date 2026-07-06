import os
from datetime import datetime, timedelta, timezone

import requests

from media_stack.constants import TRAKT_API_BASE
from media_stack.formatting import to_tsv


def _resolve_username(username: str | None) -> str | None:
    return username or os.getenv("TRAKT_USERNAME")


def _get_trakt_headers() -> dict[str, str] | str:
    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"

    return {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
    }


def check_trakt_profile_privacy(username: str | None = None) -> str:
    """Check whether a Trakt user's profile is public or private."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

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
                profile_visibility = "private"
            else:
                profile_visibility = "public"

            return f"Trakt user {username}'s profile visibility is {profile_visibility}. {details}"

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

    return f"Error: Unexpected error. Status code: {history_response.status_code}"


def get_trakt_public_watched_movies(username: str | None = None, days: int = 30) -> str:
    """Get movies watched in the last N days from a public Trakt profile."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
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

    return to_tsv(watched_movies)


def get_trakt_public_watched_shows(username: str | None = None, days: int = 30) -> str:
    """Get show episodes watched in the last N days from a public Trakt profile."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    end_at = now_utc.isoformat().replace("+00:00", "Z")

    endpoint = f"{TRAKT_API_BASE}/users/{username}/history/shows"
    params = {
        "start_at": start_at,
        "end_at": end_at,
        "limit": "1000",
        "extended": "full",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public watched shows from Trakt: {exc}"

    history_items = response.json()
    season_episode_count_cache: dict[tuple[str, int], int | None] = {}

    def _get_season_episode_count(show_ids: dict, season_number: int | None) -> int | None:
        if not isinstance(season_number, int):
            return None

        show_slug = show_ids.get("slug") if isinstance(show_ids, dict) else None
        if not show_slug:
            return None

        cache_key = (show_slug, season_number)
        if cache_key in season_episode_count_cache:
            return season_episode_count_cache[cache_key]

        season_endpoint = f"{TRAKT_API_BASE}/shows/{show_slug}/seasons/{season_number}"
        season_params = {"extended": "episodes"}

        try:
            season_response = requests.get(season_endpoint, params=season_params, headers=headers, timeout=20)
            season_response.raise_for_status()
        except requests.RequestException:
            season_episode_count_cache[cache_key] = None
            return None

        season_payload = season_response.json()
        if isinstance(season_payload, list) and season_payload:
            season_payload = season_payload[0]

        episodes = season_payload.get("episodes", []) if isinstance(season_payload, dict) else []
        total_episodes = len(episodes) if isinstance(episodes, list) else None
        season_episode_count_cache[cache_key] = total_episodes
        return total_episodes

    watched_shows: list[dict] = []
    for item in history_items:
        show = item.get("show", {})
        episode = item.get("episode", {})

        season_number = episode.get("season")
        episode_number = episode.get("number")
        season_episode_count = _get_season_episode_count(show.get("ids", {}), season_number)

        episode_position = None
        if isinstance(episode_number, int):
            if isinstance(season_episode_count, int) and season_episode_count > 0:
                episode_position = f"{episode_number}/{season_episode_count}"
            else:
                episode_position = str(episode_number)

        watched_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "season": season_number,
                "episode_position": episode_position,
                "watched_at": item.get("watched_at"),
                "episode_rating": episode.get("rating"),
                "show_rating": show.get("rating"),
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
            }
        )

    return to_tsv(watched_shows)


def get_trakt_public_liked_movies(
    username: str | None = None,
    threshold_user_rating: int = 7,
    limit: int = 50,
) -> str:
    """Get liked movies from a public Trakt profile."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(rating_value) for rating_value in range(threshold_user_rating, 11))
    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"
    params = {"limit": str(limit), "extended": "full"}

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
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(liked_movies)


def get_trakt_public_disliked_movies(
    username: str | None = None,
    threshold_user_rating: int = 6,
    limit: int = 50,
) -> str:
    """Get disliked movies from a public Trakt profile."""
    username = _resolve_username(username)
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(rating_value) for rating_value in range(1, threshold_user_rating))
    endpoint = f"{TRAKT_API_BASE}/users/{username}/ratings/movies/{rating}"
    params = {"limit": str(limit), "extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch public disliked movies from Trakt: {exc}"

    disliked_items = response.json()
    disliked_movies: list[dict] = []
    for item in disliked_items:
        movie = item.get("movie", {})
        disliked_movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(disliked_movies)


def get_trakt_latest_high_rated_movies(
    days: int = 30,
    threshold_rating: float = 7,
    limit: int = 50,
) -> str:
    """Get recently released high-rated movies from Trakt."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")

    endpoint = f"{TRAKT_API_BASE}/calendars/all/movies/{start_at}/{days}"
    params = {
        "extended": "full",
        "ratings": f"{int(threshold_rating * 10)}-100",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest movies from Trakt: {exc}"

    movies_data = response.json()[:limit]
    latest_movies: list[dict] = []
    for item in movies_data:
        movie = item.get("movie", {})
        latest_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2)
                if isinstance(movie.get("rating"), (int, float))
                else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(latest_movies)


def get_trakt_latest_high_rated_shows(
    days: int = 30,
    threshold_rating: float = 7.5,
    limit: int = 50,
) -> str:
    """Get recently aired high-rated shows from Trakt."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers
    if days <= 0:
        return "Error: days must be greater than 0"

    now_utc = datetime.now(timezone.utc)
    start_at = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d")

    endpoint = f"{TRAKT_API_BASE}/calendars/all/shows/{start_at}/{days}"
    params = {
        "extended": "full",
        "ratings": f"{int(threshold_rating * 10)}-100",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch latest shows from Trakt: {exc}"

    shows_data = response.json()[:limit]
    latest_shows: list[dict] = []
    for item in shows_data:
        show = item.get("show", {})
        latest_shows.append(
            {
                "title": show.get("title"),
                "year": show.get("year"),
                "first_aired": item.get("first_aired"),
                "runtime": str(show.get("runtime")) + " min" if show.get("runtime") else None,
                "average_rating": round(show.get("rating"), 2)
                if isinstance(show.get("rating"), (int, float))
                else None,
                "genre": show.get("genres", []),
                "certification": show.get("certification"),
                "language": show.get("language"),
                "network": show.get("network"),
                "overview": show.get("overview"),
            }
        )

    return to_tsv(latest_shows)


def get_trakt_popular_movies(limit: int = 50) -> str:
    """Get popular movies from Trakt."""
    headers = _get_trakt_headers()

    if isinstance(headers, str):
        return headers

    endpoint = f"{TRAKT_API_BASE}/movies/popular"
    params = {"extended": "full"}

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch popular movies from Trakt: {exc}"

    movies_data = response.json()[:limit]
    popular_movies: list[dict] = []
    for movie in movies_data:
        popular_movies.append(
            {
                "title": movie.get("title"),
                "release_date": movie.get("released"),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2)
                if isinstance(movie.get("rating"), (int, float))
                else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return to_tsv(popular_movies)
