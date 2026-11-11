"""Goal-based workout recommendations."""

import pytest

from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.workout_plans import (
    WorkoutPlanUnavailable,
    suggest_workout,
)


@pytest.mark.parametrize(
    ("focus", "level"),
    [
        ("core_strength", "beginner"),
        ("core_strength", "intermediate"),
        ("core_strength", "advanced"),
        ("conditioning", "beginner"),
        ("conditioning", "intermediate"),
        ("conditioning", "advanced"),
        ("fat_loss_support", "beginner"),
        ("fat_loss_support", "intermediate"),
        ("fat_loss_support", "advanced"),
    ],
)
def test_suggestions_use_catalog_exercises_and_profile_level(
    focus: str, level: str
) -> None:
    result = suggest_workout(focus, level, WORKBOOK_EXERCISES)

    assert result["focus"] == focus
    assert result["level"] == level
    assert len(result["exercises"]) >= 4
    assert all(exercise["target_sets"] == 3 for exercise in result["exercises"])
    assert all(
        exercise["tutorial_url"].startswith("https://www.youtube.com/")
        for exercise in result["exercises"]
    )
    assert all(
        exercise["prescription"]
        for exercise in result["exercises"]
    )


def test_fat_loss_suggestion_sets_realistic_expectations() -> None:
    result = suggest_workout("fat_loss_support", "beginner", WORKBOOK_EXERCISES)

    assert "garandeert geen vetverlies" in result["note"]


def test_suggestion_fails_explicitly_when_a_catalog_exercise_is_missing() -> None:
    definitions = tuple(
        exercise
        for exercise in WORKBOOK_EXERCISES
        if exercise.exercise_id != "beginner_dead_bug"
    )

    with pytest.raises(WorkoutPlanUnavailable):
        suggest_workout("core_strength", "beginner", definitions)
