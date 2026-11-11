"""YouTube instruction video links and search fallbacks for catalog exercises."""

from urllib.parse import quote_plus

_VIDEOS = {
    "beginner_push_up": "IODxDxX7oi4",
    "beginner_inverted_row_band_pull_up": "NXHOZPkn6R0",
    "beginner_plank": "pSHjTRCQxIw",
    "beginner_glute_bridge": "8bbE64NuDTU",
    "intermediate_bulgarian_split_squat": "DeCnHqrN22U",
}


def youtube_tutorial(exercise_id: str, exercise_name: str) -> dict[str, str]:
    """Return a curated video link or an exact-name YouTube tutorial search."""
    video_id = _VIDEOS.get(exercise_id)
    if video_id is not None:
        return {
            "tutorial_url": f"https://www.youtube.com/watch?v={video_id}",
            "tutorial_label": "Bekijk instructievideo",
        }

    query = quote_plus(f"{exercise_name} exercise tutorial proper form")
    return {
        "tutorial_url": f"https://www.youtube.com/results?search_query={query}",
        "tutorial_label": "Zoek instructievideo's",
    }
