"""YouTube instruction links for catalog exercises."""

from urllib.parse import unquote_plus

from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.exercise_tutorials import youtube_tutorial


def test_every_catalog_exercise_links_directly_to_a_video() -> None:
    for exercise in WORKBOOK_EXERCISES:
        tutorial = youtube_tutorial(exercise.exercise_id, exercise.name)

        assert tutorial["tutorial_url"].startswith(
            "https://www.youtube.com/watch?v="
        ), exercise.exercise_id
        assert tutorial["tutorial_label"] == "Bekijk instructievideo"


def test_selected_exercises_link_directly_to_a_tutorial() -> None:
    tutorial = youtube_tutorial("beginner_push_up", "Push-up")

    assert tutorial == {
        "tutorial_url": "https://www.youtube.com/watch?v=IODxDxX7oi4",
        "tutorial_label": "Bekijk instructievideo",
    }


def test_unknown_exercises_open_an_exact_name_tutorial_search() -> None:
    tutorial = youtube_tutorial("custom_archer_push_up", "Archer push-up")

    assert tutorial["tutorial_url"].startswith(
        "https://www.youtube.com/results?search_query="
    )
    assert "Archer push-up exercise tutorial proper form" in unquote_plus(
        tutorial["tutorial_url"]
    )
    assert tutorial["tutorial_label"] == "Zoek instructievideo's"
