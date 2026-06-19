from dotenv import load_dotenv
import os
import server

def test_check_trakt_profile_privacy():
    print(f"Testing Trakt profile privacy for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    assert server.check_trakt_profile_privacy(test_username)["profile_visibility"] == "public"
    print(f"User '{test_username}' has a public profile")

def test_get_trakt_public_watched_movies():
    print(f"Testing Trakt public watched movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    movies = server.get_trakt_public_watched_movies(test_username)
    assert isinstance(movies, list)
    assert len(movies) > 0
    print(f"Retrieved {len(movies)} watched movies for user '{test_username}'")
    print("Sample movie:", movies[0])

def test_get_trakt_public_liked_movies():
    print(f"Testing Trakt public liked movies for user '{os.getenv('TEST_TRAKT_USERNAME')}'")
    test_username = os.getenv("TEST_TRAKT_USERNAME")
    movies = server.get_trakt_public_liked_movies(test_username)
    assert isinstance(movies, list)
    assert len(movies) > 0
    print(f"Retrieved {len(movies)} liked movies for user '{test_username}'")
    print("Sample movie:", movies[0])
    assert all(movie['user_rating'] >= 7 for movie in movies)

def test_get_trakt_latest_high_rated_movies():
    print(f"Testing Trakt latest high-rated movies")
    movies = server.get_trakt_latest_high_rated_movies()
    assert isinstance(movies, list)
    assert len(movies) > 0
    print(f"Retrieved {len(movies)} latest high-rated movies from Trakt")
    print("Sample movie:", movies[0])
    assert all(movie['average_rating'] >= 7 for movie in movies)

def test_get_trakt_popular_movies():
    print(f"Testing Trakt popular movies")
    movies = server.get_trakt_popular_movies()
    assert isinstance(movies, list)
    assert len(movies) > 0
    print(f"Retrieved {len(movies)} popular movies from Trakt")
    print("Sample movie:", movies[0])

if __name__ == "__main__":
    load_dotenv("test.env")
    test_check_trakt_profile_privacy()
    test_get_trakt_public_watched_movies()
    test_get_trakt_public_liked_movies()
    test_get_trakt_latest_high_rated_movies()
    test_get_trakt_popular_movies()