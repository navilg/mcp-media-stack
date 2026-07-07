import requests

from media_stack.config import get_sonarr_config
from media_stack.formatting import to_tsv


def get_sonarr_shows() -> str:
    """Get series in Sonarr.
    INPUT: none.
    OUTPUT: TSV rows (series library metadata) or Error string.
    """
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/series"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch series from Sonarr: {exc}"

    series_data = response.json()
    series_rows: list[dict] = []
    for series in series_data:
        statistics = series.get("statistics", {})
        series_rows.append(
            {
                "title": series.get("title"),
                "year": series.get("year"),
                "monitored": series.get("monitored"),
                "status": series.get("status"),
                "path": series.get("path"),
                "season_count": len(series.get("seasons", [])),
                "episode_file_count": statistics.get("episodeFileCount"),
                "total_episode_count": statistics.get("totalEpisodeCount"),
                "size_on_disk_gb": round(statistics.get("sizeOnDisk", 0) / (1024 * 1024 * 1024), 2)
                if statistics.get("sizeOnDisk")
                else None,
                "genres": series.get("genres", []),
                "runtime": str(series.get("runtime")) + " min" if series.get("runtime") else None,
                "network": series.get("network"),
                "certification": series.get("certification"),
                "language": series.get("originalLanguage", {}).get("name"),
                "tvdb_id": series.get("tvdbId"),
                "imdb_id": series.get("imdbId"),
            }
        )

    series_rows.sort(key=lambda item: item["title"] or "")
    return to_tsv(series_rows)


def get_sonarr_quality_profiles() -> str:
    """Get Sonarr quality profiles.
    INPUT: none.
    OUTPUT: TSV rows (quality profiles) or Error string.
    """
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/qualityprofile"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch quality profiles from Sonarr: {exc}"

    quality_profiles_data = response.json()
    quality_profiles: list[dict] = []
    for profile in quality_profiles_data:
        quality_profiles.append(
            {
                "id": profile.get("id"),
                "name": profile.get("name"),
                "upgrade_allowed": profile.get("upgradeAllowed"),
                "min_format_score": profile.get("minFormatScore"),
                "cutoff_format_score": profile.get("cutoffFormatScore"),
            }
        )

    quality_profiles.sort(key=lambda profile: profile["name"] or "")
    return to_tsv(quality_profiles)


def get_sonarr_root_folders() -> str:
    """Get Sonarr root folders.
    INPUT: none.
    OUTPUT: TSV rows (root folder details) or Error string.
    """
    sonarr_config = get_sonarr_config()
    if isinstance(sonarr_config, str):
        return sonarr_config

    sonarr_url, sonarr_api_key = sonarr_config
    endpoint = f"{sonarr_url}/api/v3/rootfolder"
    headers = {"X-Api-Key": sonarr_api_key}

    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Error: Failed to fetch root folders from Sonarr: {exc}"

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
    return to_tsv(root_folders)
