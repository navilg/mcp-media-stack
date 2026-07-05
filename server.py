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

# Valid toolset names
VALID_TOOLSETS = {"radarr", "trakt"}


def _get_radarr_config() -> tuple[str, str] | str:
    radarr_url = os.getenv("RADARR_URL")
    radarr_api_key = os.getenv("RADARR_API_KEY")

    if not radarr_url:
        return "Error: RADARR_URL is not set"
    if not radarr_api_key:
        return "Error: RADARR_API_KEY is not set"

    return radarr_url.rstrip("/"), radarr_api_key


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


def _parse_toolsets(value: str) -> str:
    """Validate comma-separated toolset names. Must be valid toolsets.

    Returns the original value unchanged on success.
    Raises argparse.ArgumentTypeError on invalid input.
    """
    if not value:
        return value
    for item in value.split(","):
        t = item.strip()
        if t and t not in VALID_TOOLSETS:
            raise argparse.ArgumentTypeError(
                f"invalid toolset: '{t}'. Valid options: {', '.join(sorted(VALID_TOOLSETS))}"
            )
    return value


def _compute_tags_to_disable(disable_toolsets_arg: str) -> set[str]:
    """Compute the set of tags to disable for mcp.disable().

    Always includes 'deprecated'. Parses the comma-separated disable-toolsets
    argument and adds any valid toolset tags found. Returns a new set each call.
    """
    tags_to_disable = {"deprecated"}
    if disable_toolsets_arg:
        for tag in disable_toolsets_arg.split(","):
            t = tag.strip()
            if t:
                tags_to_disable.add(t)
    return tags_to_disable


@mcp.tool(tags={"trakt"})
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
                profile_visibility = "private"
            else:
                profile_visibility = "public"

            return f"Trakt user {username}'s profile visibility is {profile_visibility}. {details}"

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


@mcp.tool(tags={"trakt"})
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


@mcp.tool(tags={"trakt"})
def get_trakt_public_watched_shows(username: str | None = None, days: int = 30) -> str:
    """
    Get show episodes watched in the last N days from a public Trakt profile.
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

    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": trakt_client_id,
    }

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

    return _to_tsv(watched_shows)


@mcp.tool(tags={"trakt"})
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
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": movie.get("rating"),
                "user_rating": item.get("rating"),
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(liked_movies)


@mcp.tool(tags={"trakt"})
def get_trakt_public_disliked_movies(username: str | None = None, threshold_user_rating: int = 6, limit: int = 50) -> str:
    """
    Get disliked movies from a public Trakt profile.
    """

    username = username or os.getenv("TRAKT_USERNAME")

    trakt_client_id = os.getenv("TRAKT_CLIENT_ID")
    if not trakt_client_id:
        return "Error: TRAKT_CLIENT_ID is not set"
    if not username or not username.strip():
        return "Error: username must not be empty"

    rating = ",".join(str(r) for r in range(1, threshold_user_rating))  # Filter ratings less than threshold

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

    return _to_tsv(disliked_movies)


@mcp.tool(tags={"trakt"})
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
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2) if isinstance(movie.get("rating"), (int, float)) else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(latest_movies)


@mcp.tool(tags={"trakt"})
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
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "average_rating": round(movie.get("rating"), 2) if isinstance(movie.get("rating"), (int, float)) else None,
                "genre": movie.get("genres", []),
                "certification": movie.get("certification"),
                "language": movie.get("language"),
                "overview": movie.get("overview"),
            }
        )

    return _to_tsv(popular_movies)


@mcp.tool(tags={"radarr"})
def get_radarr_movies() -> str:
    """
    Get the list of movies in Radarr along with details such as whether each movie
    is monitored, whether a movie file already exists, quality profile, file size,
    genres, and more.
    """

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/movie"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch movies from Radarr: {exc}"

    movies_data = response.json()
    movies: list[dict] = []
    for movie in movies_data:
        movie_file = movie.get("movieFile", {})
        movies.append(
            {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "monitored": movie.get("monitored"),
                "status": movie.get("status"),
                "has_file": movie.get("hasFile"),
                "file_path": movie_file.get("path") if movie.get("hasFile") else None,
                "file_size_mb": round(movie_file.get("size", 0) / (1024 * 1024), 1) if movie.get("hasFile") else None,
                "quality": movie_file.get("quality", {}).get("quality", {}).get("name") if movie.get("hasFile") else None,
                "genres": movie.get("genres", []),
                "runtime": str(movie.get("runtime")) + " min" if movie.get("runtime") else None,
                "certification": movie.get("certification"),
                "tmdb_id": movie.get("tmdbId"),
                "imdb_id": movie.get("imdbId"),
            }
        )

    movies.sort(key=lambda m: m["title"] or "")
    return _to_tsv(movies)


@mcp.tool(tags={"radarr"})
def get_radarr_quality_profiles() -> str:
    """
    Get the list of Radarr quality profiles.
    """

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/qualityprofile"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch quality profiles from Radarr: {exc}"

    quality_profiles_data = response.json()
    quality_profiles: list[dict] = []
    for profile in quality_profiles_data:
        quality_profiles.append(
            {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "cutoff": profile.get("cutoff"),
                "language": profile.get("language"),
                "upgrade_allowed": profile.get("upgradeAllowed"),
            }
        )

    quality_profiles.sort(key=lambda profile: profile["name"] or "")
    return _to_tsv(quality_profiles)


@mcp.tool(tags={"radarr"})
def get_radarr_root_folders() -> str:
    """
    Get the list of Radarr root folders.
    """

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/rootfolder"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch root folders from Radarr: {exc}"

    root_folders_data = response.json()
    root_folders: list[dict] = []
    for folder in root_folders_data:
        root_folders.append(
            {
                "id": folder.get("id"),
                "path": folder.get("path"),
                "free_space_gb": round(folder.get("freeSpace", 0) / (1024 * 1024 * 1024), 2),
                "accessible": folder.get("accessible"),
                "default": folder.get("default"),
            }
        )

    root_folders.sort(key=lambda folder: folder["path"] or "")
    return _to_tsv(root_folders)


@mcp.tool(tags={"radarr"})
def add_radarr_movie(movie_query: str, root_folder_path: str, quality_profile_id: int) -> str:
    """
    Add a movie to Radarr using the provided root folder and quality profile.

    The movie is added with monitor set to movieOnly, minimum availability set to
    released, and searchForMovie enabled.
    """

    if not movie_query or not movie_query.strip():
        return "Error: movie_query must not be empty"
    if not root_folder_path or not root_folder_path.strip():
        return "Error: root_folder_path must not be empty"

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    lookup_endpoint = f"{radarr_url}/api/v3/movie/lookup"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": movie_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up movie in Radarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Radarr movie match found for '{movie_query}'"

    selected_movie = None
    normalized_query = movie_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_movie = candidate
            break

    if selected_movie is None:
        selected_movie = lookup_results[0]

    movie_payload = dict(selected_movie)
    movie_payload["monitored"] = True
    movie_payload["monitorNewItems"] = "movieOnly"
    movie_payload["minimumAvailability"] = "released"
    movie_payload["rootFolderPath"] = root_folder_path
    movie_payload["qualityProfileId"] = quality_profile_id
    movie_payload["addOptions"] = {"searchForMovie": True}

    try:
        add_response = requests.post(
            f"{radarr_url}/api/v3/movie",
            json=movie_payload,
            headers=headers,
            timeout=20,
        )
        add_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to add movie to Radarr: {exc}"

    added_movie = add_response.json() if add_response.content else movie_payload
    added_title = added_movie.get("title") or movie_payload.get("title") or movie_query.strip()
    added_path = added_movie.get("path") or root_folder_path
    return f"Added Radarr movie '{added_title}' at '{added_path}' with quality profile {quality_profile_id}"


@mcp.tool(tags={"radarr"})
def delete_radarr_movie(movie_query: str, delete_files: bool = False) -> str:
    """
    Delete a movie from Radarr.

    The movie is resolved by lookup query first. Set delete_files to True to
    remove the movie file from disk as well.
    """

    if not movie_query or not movie_query.strip():
        return "Error: movie_query must not be empty"

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    lookup_endpoint = f"{radarr_url}/api/v3/movie/lookup"
    headers = {"X-Api-Key": radarr_api_key}

    try:
        lookup_response = requests.get(
            lookup_endpoint,
            params={"term": movie_query.strip()},
            headers=headers,
            timeout=20,
        )
        lookup_response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to look up movie in Radarr: {exc}"

    lookup_results = lookup_response.json()
    if not lookup_results:
        return f"Error: No Radarr movie match found for '{movie_query}'"

    selected_movie = None
    normalized_query = movie_query.strip().lower()
    for candidate in lookup_results:
        candidate_title = str(candidate.get("title", "")).strip().lower()
        candidate_title_slug = str(candidate.get("titleSlug", "")).strip().lower()
        if normalized_query == candidate_title or normalized_query == candidate_title_slug:
            selected_movie = candidate
            break

    if selected_movie is None:
        selected_movie = lookup_results[0]

    movie_id = selected_movie.get("id")
    movie_title = selected_movie.get("title") or movie_query.strip()
    if movie_id is None:
        return f"Error: Radarr lookup for '{movie_title}' did not include a movie id"

    delete_endpoint = f"{radarr_url}/api/v3/movie/{movie_id}"

    try:
        response = requests.delete(
            delete_endpoint,
            params={"deleteFiles": str(delete_files).lower()},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to delete movie from Radarr: {exc}"

    return f"Deleted Radarr movie '{movie_title}' (delete_files={delete_files})"


@mcp.tool(tags={"radarr"})
def get_radarr_current_downloads() -> str:
    """
    Get the movies that are currently downloading in Radarr with progress and ETA.
    """

    radarr_config = _get_radarr_config()
    if isinstance(radarr_config, str):
        return radarr_config

    radarr_url, radarr_api_key = radarr_config
    endpoint = f"{radarr_url}/api/v3/queue"
    headers = {"X-Api-Key": radarr_api_key}
    params = {
        "page": 1,
        "pageSize": 1000,
        "sortKey": "title",
        "sortDirection": "ascending",
    }

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch current downloads from Radarr: {exc}"

    queue_data = response.json()
    queue_items = queue_data.get("records", queue_data) if isinstance(queue_data, dict) else queue_data

    downloads: list[dict] = []
    for item in queue_items:
        if str(item.get("status", "")).lower() != "downloading":
            continue

        size = item.get("size")
        size_left = item.get("sizeLeft")
        progress = None
        if isinstance(size, (int, float)) and size > 0 and isinstance(size_left, (int, float)):
            progress = round(((size - size_left) / size) * 100, 1)

        downloads.append(
            {
                "title": item.get("title"),
                "status": item.get("status"),
                "protocol": item.get("protocol"),
                "progress_percent": progress,
                "size_left_bytes": size_left,
                "time_left": item.get("timeleft"),
                "estimated_completion_time": item.get("estimatedCompletionTime"),
                "download_id": item.get("downloadId"),
            }
        )

    downloads.sort(key=lambda download: download["title"] or "")
    return _to_tsv(downloads)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--transport", type=str, default="streamable-http", help="Transport protocol to use (default: streamable-http)")
    args = parser.parse_args()

    # Always disable the "deprecated" tag; add any toolsets from DISABLE_TOOLSETS environment variable
    disable_toolsets_env = os.getenv("DISABLE_TOOLSETS", "")
    _parse_toolsets(disable_toolsets_env)  # Validate the environment variable
    tags_to_disable = _compute_tags_to_disable(disable_toolsets_env)

    mcp.disable(tags=tags_to_disable)

    mcp.run(transport=args.transport, host=args.host, port=args.port)