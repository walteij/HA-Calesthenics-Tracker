"""YouTube instruction video links and search fallbacks for catalog exercises."""

from urllib.parse import quote_plus

_VIDEOS = {
    "beginner_push_up": "IODxDxX7oi4",
    "beginner_inverted_row_band_pull_up": "NXHOZPkn6R0",
    "beginner_bodyweight_squat": "P-yaD24bUE8",
    "beginner_walking_lunge": "vYfp2t4XgqQ",
    "beginner_plank": "pSHjTRCQxIw",
    "beginner_glute_bridge": "8bbE64NuDTU",
    "beginner_dead_bug": "bxn9FBrt4-A",
    "beginner_side_plank": "44ND4bOB-T0",
    "beginner_hollow_body_hold": "0yPin8hSc8o",
    "beginner_jumping_jack": "uLVt6u15L98",
    "beginner_mountain_climber": "cnyTQDSE884",
    "beginner_high_knees": "dKkACF_lgaQ",
    "beginner_burpee": "Uzby_714akU",
    "intermediate_feet_elevated_push_up": "4aUUcfwyfE0",
    "intermediate_parallel_bar_dip": "WKr0rQPLVbc",
    "intermediate_pike_push_up": "shEnAXgc9y4",
    "intermediate_pull_up": "eudAs_DtWLg",
    "intermediate_chin_up": "mRy9m2Q9_1I",
    "intermediate_feet_elevated_inverted_row": "44W1JgF0lyQ",
    "intermediate_bulgarian_split_squat": "DeCnHqrN22U",
    "intermediate_pistol_squat_negative": "YMvPC1byyGo",
    "intermediate_assisted_nordic_curl": "--VA6eM2rxI",
    "advanced_hanging_knee_raise": "IHOFHNWn0_M",
    "advanced_muscle_up_progression": "-IIAQV-Mse0",
    "advanced_one_arm_pull_up_progression": "mTJHClMQPM8",
    "advanced_front_lever_progression": "rx0vr-teG7M",
    "advanced_pistol_squat_progression": "T74bU2vNWG4",
    "advanced_weighted_dip": "UZ_kEpmACZ4",
    "advanced_weighted_pull_up": "ZGKvodKT6Q0",
    "advanced_weighted_pistol_squat": "7rRXwdPs8Sk",
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
