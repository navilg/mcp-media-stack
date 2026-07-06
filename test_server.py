import argparse
import subprocess
import sys
from dotenv import load_dotenv
import os

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


def _set_env(overrides: dict[str, str | None]) -> dict[str, str | None]:
    """Temporarily set/unset env vars and return previous values for restore."""
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    """Restore env vars previously captured by _set_env."""
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value




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
    try:
        server._parse_toolsets("invalid_toolset")
        assert False, "Expected argparse.ArgumentTypeError for invalid toolset"
    except argparse.ArgumentTypeError as exc:
        assert "invalid toolset: 'invalid_toolset'" in str(exc)

    try:
        server._parse_toolsets("trakt,bogus")
        assert False, "Expected argparse.ArgumentTypeError for invalid toolset in list"
    except argparse.ArgumentTypeError as exc:
        assert "invalid toolset: 'bogus'" in str(exc)


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


def test_server_help_does_not_mention_disable_toolsets_flag():
    """The --help output should not reference the removed --disable-toolsets flag."""
    result = subprocess.run(
        [sys.executable, "server.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "--disable-toolsets" not in result.stdout


def test_server_with_invalid_disable_toolsets_env_fails():
    """Passing an invalid DISABLE_TOOLSETS value should exit with an error."""
    env = os.environ.copy()
    env["DISABLE_TOOLSETS"] = "bogus"
    result = subprocess.run(
        [sys.executable, "server.py"],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
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


def test_get_trakt_public_watched_shows():
    print(f"\nTesting Trakt public watched shows for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    result_tsv = server.get_trakt_public_watched_shows(test_username)
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} watched shows for user '{test_username}'")
    print("Sample show:", records[0])

def test_get_trakt_public_watched_shows_validation_errors():
    print("\nTesting Trakt public watched shows validation")

    previous = _set_env({"TRAKT_CLIENT_ID": None})
    try:
        result = server.get_trakt_public_watched_shows("test-user")
        assert result == "Error: TRAKT_CLIENT_ID is not set"
    finally:
        _restore_env(previous)

    previous = _set_env({"TRAKT_CLIENT_ID": "test-client-id"})
    try:
        result = server.get_trakt_public_watched_shows("   ")
        assert result == "Error: username must not be empty"
    finally:
        _restore_env(previous)

    previous = _set_env({"TRAKT_CLIENT_ID": "test-client-id"})
    try:
        result = server.get_trakt_public_watched_shows("test-user", days=0)
        assert result == "Error: days must be greater than 0"
    finally:
        _restore_env(previous)


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


def test_get_trakt_latest_high_rated_shows():
    print("\nTesting Trakt latest high-rated shows")

    result_tsv = server.get_trakt_latest_high_rated_shows(days=7, threshold_rating=7.5, limit=10)

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} latest high-rated shows from Trakt")
    print("Sample show:", records[0])
    assert all(float(record["average_rating"]) >= 7.5 for record in records)


def test_get_trakt_popular_movies():
    print(f"\nTesting Trakt popular movies")
    result_tsv = server.get_trakt_popular_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} popular movies from Trakt")
    print("Sample movie:", records[0])


def test_get_trakt_trending_movies():
    print("\nTesting Trakt trending movies")

    result_tsv = server.get_trakt_trending_movies()
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    assert len(records) <= 20
    print(f"Retrieved {len(records)} trending movies from Trakt")
    print("Sample movie:", records[0])


def test_get_trakt_popular_shows():
    print("\nTesting Trakt popular shows")

    result_tsv = server.get_trakt_popular_shows(limit=10)

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} popular shows from Trakt")
    print("Sample show:", records[0])

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

    result_tsv = server.get_radarr_quality_profiles()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} quality profiles from Radarr")
    print("Sample quality profile:", records[0])
    assert "id" in records[0]
    assert "name" in records[0]


def test_get_radarr_root_folders():
    print("\nTesting Radarr root folders list")

    result_tsv = server.get_radarr_root_folders()

    assert not result_tsv.startswith("Error:"), f"Tool returned an error: {result_tsv}"
    records = _parse_tsv(result_tsv)
    assert len(records) > 0
    print(f"Retrieved {len(records)} root folders from Radarr")
    print("Sample root folder:", records[0])
    assert "id" in records[0]
    assert "path" in records[0]




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
    test_check_trakt_profile_privacy()
    test_get_trakt_public_watched_movies()
    test_get_trakt_public_liked_movies()
    test_get_trakt_public_disliked_movies()
    test_get_trakt_latest_high_rated_movies()
    test_get_trakt_latest_high_rated_shows()
    test_get_trakt_popular_movies()
    test_get_trakt_trending_movies()
    test_get_trakt_popular_shows()
    test_get_radarr_movies()
    test_get_radarr_quality_profiles()
    test_get_radarr_root_folders()
    test_get_trakt_public_watched_shows()
    test_get_trakt_public_watched_shows_validation_errors()
