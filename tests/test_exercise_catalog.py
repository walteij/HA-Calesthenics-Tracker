"""Exercise catalog definitions."""

from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES


def test_catalog_contains_unique_exercises_without_assumed_ab_split() -> None:
    assert len(WORKBOOK_EXERCISES) == 30
    assert len({exercise.exercise_id for exercise in WORKBOOK_EXERCISES}) == 30
    assert {exercise.level for exercise in WORKBOOK_EXERCISES} == {
        "beginner",
        "intermediate",
        "advanced",
    }
    assert all(exercise.session_type is None for exercise in WORKBOOK_EXERCISES)


def test_catalog_preserves_workbook_tempo_and_phase_prescriptions() -> None:
    beginner_push_up = next(
        exercise
        for exercise in WORKBOOK_EXERCISES
        if exercise.exercise_id == "beginner_push_up"
    )
    advanced_pull_up = next(
        exercise
        for exercise in WORKBOOK_EXERCISES
        if exercise.exercise_id == "advanced_weighted_pull_up"
    )
    assert beginner_push_up.tempo == "2-0-1"
    assert beginner_push_up.minimum_repetitions == 8
    assert beginner_push_up.maximum_repetitions == 12
    assert advanced_pull_up.prescription == "4 x 8-12 (phase 1) -> 5 x 4-6 (phase 2)"
