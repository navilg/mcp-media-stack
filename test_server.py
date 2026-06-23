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


if __name__ == "__main__":
    load_dotenv("test.env")
    test_check_trakt_profile_privacy()
    test_get_trakt_public_watched_movies()
    test_get_trakt_public_liked_movies()
    test_get_trakt_public_disliked_movies()
    test_get_trakt_latest_high_rated_movies()
    test_get_trakt_popular_movies()
