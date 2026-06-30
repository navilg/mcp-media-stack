import argparse
import subprocess
import sys
from dotenv import load_dotenv
import os
from unittest.mock import patch

import pytest
import requests
import server


def _parse_tsv(tsv_str: str) -> list[dict]:
    """Parse a TSV string into a list of dicts."""
    if not tsv_str or not tsv_str.strip():
        return []
    lines = tsv_str.strip().split("\n")
    headers = lines[0].split("\t")
    records = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split("\t")
        record = {}
        for i, header in enumerate(headers):
            record[header] = values[i] if i < len(values) else ""
        records.append(record)
    return records


class _MockResponse:
    def __init__(self, json_data, status_code: int = 200, content: bytes | None = None):
        self._json_data = json_data
        self.status_code = status_code
        self.content = content if content is not None else b""

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


# ---------------------------------------------------------------------------
# Toolset / tag parsing tests (no network required)
# ---------------------------------------------------------------------------


def test_valid_toolsets():
    """Valid toolset names pass validation."""
    assert server._parse_toolsets("") == ""
    assert server._parse_toolsets("trakt") == "trakt"
    assert server._parse_toolsets("radarr") == "radarr"
    assert server._parse_toolsets("trakt,radarr") == "trakt,radarr"
    assert server._parse_toolsets("radarr,trakt") == "radarr,trakt"


def test_parse_toolsets_handles_whitespace():
    """Whitespace around toolset names is tolerated."""
    assert server._parse_toolsets("  trakt  ") == "  trakt  "
    assert server._parse_toolsets(" trakt , radarr ") == " trakt , radarr "


def test_parse_toolsets_invalid():
    """Unknown toolset names raise ArgumentTypeError."""
    with pytest.raises(argparse.ArgumentTypeError, match="invalid toolset: 'invalid_toolset'"):
        server._parse_toolsets("invalid_toolset")

    with pytest.raises(argparse.ArgumentTypeError, match="invalid toolset: 'bogus'"):
        server._parse_toolsets("trakt,bogus")


def test_compute_tags_to_disable_default():
    """Default (empty string) results in only 'deprecated'."""
    tags = server._compute_tags_to_disable("")
    assert tags == {"deprecated"}


def test_compute_tags_to_disable_with_trakt():
    """Disabling 'trakt' adds it to the deprecated tag."""
    tags = server._compute_tags_to_disable("trakt")
    assert tags == {"deprecated", "trakt"}


def test_compute_tags_to_disable_with_radarr():
    """Disabling 'radarr' adds it to the deprecated tag."""
    tags = server._compute_tags_to_disable("radarr")
    assert tags == {"deprecated", "radarr"}


def test_compute_tags_to_disable_both():
    """Disabling both toolsets includes all three tags."""
    tags = server._compute_tags_to_disable("trakt,radarr")
    assert tags == {"deprecated", "trakt", "radarr"}


def test_compute_tags_to_disable_handles_whitespace():
    """Whitespace in the CSV argument is stripped."""
    tags = server._compute_tags_to_disable("  trakt , radarr  ")
    assert tags == {"deprecated", "trakt", "radarr"}


def test_compute_tags_to_disable_returns_fresh_set():
    """Each call returns a new set, no aliasing."""
    tags1 = server._compute_tags_to_disable("trakt")
    tags2 = server._compute_tags_to_disable("radarr")
    assert tags1 != tags2


# ---------------------------------------------------------------------------
# CLI integration tests (subprocess)
# ---------------------------------------------------------------------------


def test_server_help_mentions_disable_toolsets():
    """The --help output should reference --disable-toolsets."""
    result = subprocess.run(
        [sys.executable, "server.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--disable-toolsets" in result.stdout


def test_server_help_lists_radarr_and_trakt():
    """The --help output should mention radarr and trakt as valid options."""
    result = subprocess.run(
        [sys.executable, "server.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "radarr" in result.stdout or "radarr" in result.stderr
    assert "trakt" in result.stdout or "trakt" in result.stderr


def test_server_with_invalid_toolset_fails():
    """Passing an invalid toolset name should exit with an error."""
    result = subprocess.run(
        [sys.executable, "server.py", "--disable-toolsets", "bogus"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "invalid toolset" in result.stderr


# ---------------------------------------------------------------------------
# Existing integration tests (unchanged, below)
# ---------------------------------------------------------------------------


def test_check_trakt_profile_privacy():
    print(f"\nTesting Trakt profile privacy for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result = server.check_trakt_profile_privacy(test_username)
    assert isinstance(result, str)
    assert "visibility is public" in result
    print(f"User '{test_username}' has a public profile")


def test_get_trakt_public_watched_movies():
    print(f"\nTesting Trakt public watched movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_watched_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} watched movies for user '{test_username}'")
    print("Sample movie:", records[0])


def test_get_trakt_public_liked_movies():
    print(f"\nTesting Trakt public liked movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_liked_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} liked movies for user '{test_username}'")
    print("Sample movie:", records[0])
    assert all(int(record["user_rating"]) >= 7 for record in records)


def test_get_trakt_public_disliked_movies():
    print(f"\nTesting Trakt public disliked movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_disliked_movies(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} disliked movies for user '{test_username}'")
    print("Sample movie:", records[0])
    assert all(int(record["user_rating"]) <= 5 for record in records)


def test_get_trakt_latest_high_rated_movies():
    print(f"\nTesting Trakt latest high-rated movies")
    result_tsv = server.get_trakt_latest_high_rated_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} latest high-rated movies from Trakt")
    print("Sample movie:", records[0])
    assert all(float(record["average_rating"]) >= 7 for record in records)


def test_get_trakt_popular_movies():
    print(f"\nTesting Trakt popular movies")
    result_tsv = server.get_trakt_popular_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} popular movies from Trakt")
    print("Sample movie:", records[0])


def test_get_radarr_movies():
    print("\nTesting Radarr movies list")
    result_tsv = server.get_radarr_movies()
    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0, "Expected at least one movie in Radarr"
    print(f"Retrieved {len(records)} movies from Radarr")
    print("Sample movie:", records[0])
    assert "title" in records[0]
    assert "monitored" in records[0]
    assert "has_file" in records[0]


def test_get_radarr_quality_profiles():
    print("\nTesting Radarr quality profiles list")
    sample_profiles = [
        {"id": 1, "name": "HD-1080p", "cutoff": 1, "language": "English", "upgradeAllowed": True},
        {"id": 2, "name": "HD-2160p", "cutoff": 2, "language": "English", "upgradeAllowed": True},
    ]

    with patch.object(server.requests, "get", return_value=_MockResponse(sample_profiles)):
        result_tsv = server.get_radarr_quality_profiles()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) == 2
    print(f"Retrieved {len(records)} quality profiles from Radarr")
    print("Sample quality profile:", records[0])
    assert "id" in records[0]
    assert "name" in records[0]


def test_get_radarr_root_folders():
    print("\nTesting Radarr root folders list")
    sample_root_folders = [
        {"id": 1, "path": "/media/movies", "freeSpace": 536870912000, "accessible": True, "default": True},
        {"id": 2, "path": "/media/archive", "freeSpace": 107374182400, "accessible": True, "default": False},
    ]

    with patch.object(server.requests, "get", return_value=_MockResponse(sample_root_folders)):
        result_tsv = server.get_radarr_root_folders()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) == 2
    print(f"Retrieved {len(records)} root folders from Radarr")
    print("Sample root folder:", records[0])
    assert "id" in records[0]
    assert "path" in records[0]


def test_add_radarr_movie():
    print("\nTesting Radarr add movie")
    lookup_results = [
        {"title": "Dune", "titleSlug": "dune-2021", "year": 2021, "tmdbId": 12345, "monitored": False}
    ]
    captured_payload = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/api/v3/movie/lookup")
        assert params == {"term": "Dune"}
        return _MockResponse(lookup_results)

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url.endswith("/api/v3/movie")
        captured_payload.update(json or {})
        response_body = dict(json or {})
        response_body["path"] = (json or {}).get("rootFolderPath")
        return _MockResponse(response_body, content=b"{}")

    with patch.object(server.requests, "get", side_effect=fake_get), patch.object(server.requests, "post", side_effect=fake_post):
        result = server.add_radarr_movie("Dune", "/media/movies", 7)

    assert "Added Radarr movie 'Dune'" in result
    assert "/media/movies" in result
    assert captured_payload["monitored"] is True
    assert captured_payload["monitorNewItems"] == "movieOnly"
    assert captured_payload["minimumAvailability"] == "released"
    assert captured_payload["rootFolderPath"] == "/media/movies"
    assert captured_payload["qualityProfileId"] == 7
    assert captured_payload["addOptions"] == {"searchForMovie": True}


def test_delete_radarr_movie():
    print("\nTesting Radarr delete movie")
    lookup_results = [
        {"id": 42, "title": "Dune", "titleSlug": "dune-2021", "year": 2021, "tmdbId": 12345}
    ]
    captured_params = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/api/v3/movie/lookup")
        assert params == {"term": "Dune"}
        return _MockResponse(lookup_results)

    def fake_delete(url, params=None, headers=None, timeout=None):
        assert url.endswith("/api/v3/movie/42")
        captured_params.update(params or {})
        return _MockResponse({}, content=b"{}")

    with patch.object(server.requests, "get", side_effect=fake_get), patch.object(server.requests, "delete", side_effect=fake_delete):
        result = server.delete_radarr_movie("Dune", delete_files=True)

    assert result == "Deleted Radarr movie 'Dune' (delete_files=True)"
    assert captured_params == {"deleteFiles": "true"}


def test_get_radarr_current_downloads():
    print("\nTesting Radarr current downloads")
    queue_payload = {
        "records": [
            {
                "title": "Dune",
                "status": "downloading",
                "protocol": "usenet",
                "size": 1000,
                "sizeLeft": 250,
                "timeleft": "00:15:00",
                "estimatedCompletionTime": "2026-06-29T18:15:00Z",
                "downloadId": "abc123",
            },
            {
                "title": "Not Downloading",
                "status": "completed",
                "protocol": "usenet",
                "size": 1000,
                "sizeLeft": 0,
                "timeleft": "00:00:00",
                "estimatedCompletionTime": "2026-06-29T18:00:00Z",
                "downloadId": "zzz999",
            },
        ]
    }

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/api/v3/queue")
        assert params == {
            "page": 1,
            "pageSize": 1000,
            "sortKey": "title",
            "sortDirection": "ascending",
        }
        return _MockResponse(queue_payload)

    with patch.object(server.requests, "get", side_effect=fake_get):
        result_tsv = server.get_radarr_current_downloads()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) == 1
    assert records[0]["title"] == "Dune"
    assert records[0]["progress_percent"] == "75.0"
    assert records[0]["time_left"] == "00:15:00"
    print("Retrieved current download:", records[0])


if __name__ == "__main__":
    load_dotenv("test.env")
    test_valid_toolsets()
    test_parse_toolsets_handles_whitespace()
    test_parse_toolsets_invalid()
    test_compute_tags_to_disable_default()
    test_compute_tags_to_disable_with_trakt()
    test_compute_tags_to_disable_with_radarr()
    test_compute_tags_to_disable_both()
    test_compute_tags_to_disable_handles_whitespace()
    test_compute_tags_to_disable_returns_fresh_set()
    test_server_help_mentions_disable_toolsets()
    test_server_help_lists_radarr_and_trakt()
    test_server_with_invalid_toolset_fails()
    test_check_trakt_profile_privacy()
    test_get_trakt_public_watched_movies()
    test_get_trakt_public_liked_movies()
    test_get_trakt_public_disliked_movies()
    test_get_trakt_latest_high_rated_movies()
    test_get_trakt_popular_movies()
    test_get_radarr_movies()
    test_get_radarr_quality_profiles()
    test_get_radarr_root_folders()
    test_add_radarr_movie()
    test_delete_radarr_movie()
    test_get_radarr_current_downloads()