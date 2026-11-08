"""Progression and graduation policies operate only on completed exercise logs."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.calisthenics_tracker.exercise_catalog import WORKBOOK_EXERCISES
from custom_components.calisthenics_tracker.models import ExerciseLog, Workout
from custom_components.calisthenics_tracker.progression import (
    GraduationStatus,
    ProgressionStatus,
    analyze_exercise_progress,
    beginner_graduation_readiness,
)

UTC = ZoneInfo("UTC")
EXERCISE_ID = "beginner_push_up"
DEFINITIONS = WORKBOOK_EXERCISES


def _workout(
    index: int,
    exercise_id: str = EXERCISE_ID,
    *,
    variant: str = "Strict push-up",
    sets: tuple[int | float, ...] = (8, 8, 8),
    rir: int = 2,
    pain_score: int = 0,
    status: str = "completed",
) -> Workout:
    completed = datetime(2026, 11, 1, 10, tzinfo=UTC) + timedelta(days=index)
    return Workout(
        workout_id=f"00000000-0000-0000-0000-{index + 1:012d}",
        session_type="A",
        started_at=completed - timedelta(minutes=30),
        completed_at=completed if status == "completed" else None,
        duration_minutes=30 if status == "completed" else None,
        status=status,
        exercises=(
            ExerciseLog(
                exercise_id=exercise_id,
                variant=variant,
                sets=sets,
                rir=rir,
                pain_score=pain_score,
            ),
        ),
    )


def _status(*workouts: Workout) -> ProgressionStatus:
    return analyze_exercise_progress(EXERCISE_ID, DEFINITIONS, tuple(workouts)).status


def test_progression_needs_three_comparable_completed_performances() -> None:
    assert _status(_workout(1), _workout(2, status="active")) is (
        ProgressionStatus.INSUFFICIENT_DATA
    )
    assert (
        _status(
            _workout(1, variant="Incline push-up"),
            _workout(2, variant="Strict push-up"),
            _workout(3, variant="Strict push-up"),
        )
        is ProgressionStatus.INSUFFICIENT_DATA
    )


def test_progression_ready_requires_two_max_rep_sessions_and_safe_rir() -> None:
    assert (
        _status(
            _workout(1, sets=(8, 8, 8)),
            _workout(2, sets=(12, 12, 12)),
            _workout(3, sets=(12, 12, 12), rir=1),
        )
        is ProgressionStatus.PROGRESSION_READY
    )
    assert (
        _status(
            _workout(1, sets=(8, 8, 8)),
            _workout(2, sets=(12, 12, 12), rir=0),
            _workout(3, sets=(12, 12, 12), rir=1),
        )
        is ProgressionStatus.PROGRESSING
    )


def test_progression_detects_progressing_maintaining_and_plateau() -> None:
    assert (
        _status(
            _workout(1, sets=(8, 8, 8)),
            _workout(2, sets=(9, 8, 8)),
            _workout(3, sets=(10, 8, 8)),
        )
        is ProgressionStatus.PROGRESSING
    )
    assert (
        _status(
            _workout(1, sets=(9, 9, 9)),
            _workout(2, sets=(9, 8, 9)),
            _workout(3, sets=(9, 8, 8)),
        )
        is ProgressionStatus.MAINTAINING
    )
    assert _status(_workout(1), _workout(2), _workout(3)) is (ProgressionStatus.PLATEAU)


def test_one_bad_session_does_not_create_plateau() -> None:
    assert (
        _status(
            _workout(1, sets=(10, 10, 10)),
            _workout(2, sets=(10, 10, 10)),
            _workout(3, sets=(8, 8, 8)),
        )
        is ProgressionStatus.MAINTAINING
    )


def test_regression_uses_pain_or_repeated_minimum_repetition_failures() -> None:
    assert (
        _status(
            _workout(1, sets=(8, 8, 8)),
            _workout(2, sets=(8, 8, 8)),
            _workout(3, sets=(8, 8, 8), pain_score=4),
        )
        is ProgressionStatus.REGRESSION_RECOMMENDED
    )
    assert (
        _status(
            _workout(1, sets=(7, 8, 8)),
            _workout(2, sets=(7, 7, 8)),
            _workout(3, sets=(8, 8, 8)),
        )
        is ProgressionStatus.REGRESSION_RECOMMENDED
    )


def _graduation_workout(
    index: int, exercise_id: str, variant: str, reps: int
) -> Workout:
    return _workout(
        index,
        exercise_id,
        variant=variant,
        sets=(reps,),
    )


def test_beginner_graduation_requires_explicit_strict_variants() -> None:
    workouts = (
        _graduation_workout(1, "beginner_push_up", "Strict push-up", 15),
        _graduation_workout(2, "intermediate_pull_up", "Dead-hang pull-up", 5),
        _graduation_workout(
            3, "beginner_bodyweight_squat", "Strict full-depth squat", 20
        ),
    )
    result = beginner_graduation_readiness(workouts)
    assert result.status is GraduationStatus.GRADUATION_READY
    assert (
        result.push_ups,
        result.dead_hang_pull_ups,
        result.strict_full_depth_squats,
    ) == (
        15,
        5,
        20,
    )


def test_beginner_graduation_near_ready_requires_each_qualified_criterion() -> None:
    workouts = (
        _graduation_workout(1, "beginner_push_up", "Strict push-up", 12),
        _graduation_workout(2, "intermediate_pull_up", "Dead hang pull up", 4),
        _graduation_workout(
            3, "beginner_bodyweight_squat", "Strict full depth squat", 16
        ),
    )
    assert (
        beginner_graduation_readiness(workouts).status is GraduationStatus.NEARLY_READY
    )


def test_beginner_graduation_accepts_spaced_and_joined_plural_variants() -> None:
    workouts = (
        _graduation_workout(1, "beginner_push_up", "Strict pushups", 15),
        _graduation_workout(2, "intermediate_pull_up", "Dead-hang pullups", 5),
        _graduation_workout(
            3, "beginner_bodyweight_squat", "Strict full-depth squats", 20
        ),
    )
    assert (
        beginner_graduation_readiness(workouts).status
        is GraduationStatus.GRADUATION_READY
    )


def test_graduation_ignores_unqualified_variants_and_active_workouts() -> None:
    workouts = (
        _graduation_workout(1, "beginner_push_up", "Incline push-up", 30),
        _graduation_workout(2, "intermediate_pull_up", "Chin-up", 20),
        _graduation_workout(3, "beginner_bodyweight_squat", "Box squat", 40),
        _workout(
            4,
            "beginner_push_up",
            variant="Strict push-up",
            sets=(30,),
            status="active",
        ),
    )
    result = beginner_graduation_readiness(workouts)
    assert result.status is GraduationStatus.NOT_READY
    assert result.push_ups is None
    assert result.dead_hang_pull_ups is None
    assert result.strict_full_depth_squats is None
