"""Curated goal-based workout suggestions built from the exercise catalog."""

from typing import Any

from .const import LEVELS, WORKOUT_FOCI
from .exercise_tutorials import youtube_tutorial
from .models import ExerciseDefinition

_PLANS: dict[str, dict[str, tuple[str, ...]]] = {
    "core_strength": {
        "beginner": (
            "beginner_dead_bug",
            "beginner_plank",
            "beginner_side_plank",
            "beginner_glute_bridge",
        ),
        "intermediate": (
            "beginner_dead_bug",
            "beginner_hollow_body_hold",
            "beginner_side_plank",
            "beginner_mountain_climber",
        ),
        "advanced": (
            "advanced_hanging_knee_raise",
            "beginner_hollow_body_hold",
            "beginner_side_plank",
            "beginner_mountain_climber",
        ),
    },
    "conditioning": {
        "beginner": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_bodyweight_squat",
            "beginner_mountain_climber",
        ),
        "intermediate": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_mountain_climber",
            "beginner_burpee",
        ),
        "advanced": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_burpee",
            "intermediate_pike_push_up",
        ),
    },
    "fat_loss_support": {
        "beginner": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_bodyweight_squat",
            "beginner_mountain_climber",
            "beginner_glute_bridge",
        ),
        "intermediate": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_mountain_climber",
            "beginner_burpee",
            "intermediate_pike_push_up",
        ),
        "advanced": (
            "beginner_jumping_jack",
            "beginner_high_knees",
            "beginner_burpee",
            "intermediate_pike_push_up",
            "beginner_glute_bridge",
        ),
    },
}

_TITLES = {
    "core_strength": "Corekracht",
    "conditioning": "Conditie",
    "fat_loss_support": "Conditie voor ondersteuning van vetverlies",
}
_FORMATS = {
    "core_strength": (
        "Circuit van 3 rondes. Rust 45-60 seconden tussen oefeningen."
    ),
    "conditioning": (
        "Circuit van 3 rondes. Houd je techniek strak; rust 60-90 seconden na "
        "iedere ronde."
    ),
    "fat_loss_support": (
        "Circuit van 3 rondes. Houd je techniek strak; rust 60-90 seconden na "
        "iedere ronde."
    ),
}
_NOTES = {
    "core_strength": "",
    "conditioning": "",
    "fat_loss_support": (
        "Training kan het energieverbruik ondersteunen, maar garandeert geen "
        "vetverlies; voeding en de energiebalans op langere termijn spelen ook mee."
    ),
}


class WorkoutPlanUnavailable(ValueError):
    """Raised when a curated plan references an unavailable exercise."""


def suggest_workout(
    focus: str,
    level: str,
    definitions: tuple[ExerciseDefinition, ...],
) -> dict[str, Any]:
    """Return one curated routine with its catalog prescriptions."""
    if focus not in WORKOUT_FOCI or level not in LEVELS:
        raise ValueError("Unsupported workout focus or level")
    by_id = {definition.exercise_id: definition for definition in definitions}
    exercise_ids = _PLANS[focus][level]
    missing_ids = [
        exercise_id for exercise_id in exercise_ids if exercise_id not in by_id
    ]
    if missing_ids:
        raise WorkoutPlanUnavailable(
            f"Workout plan references missing exercises: {', '.join(missing_ids)}"
        )

    return {
        "focus": focus,
        "level": level,
        "title": _TITLES[focus],
        "format": _FORMATS[focus],
        "note": _NOTES[focus],
        "exercises": [
            {
                "exercise_id": definition.exercise_id,
                "name": definition.name,
                "prescription": definition.prescription,
                "target_sets": definition.target_sets,
                "minimum_repetitions": definition.minimum_repetitions,
                "maximum_repetitions": definition.maximum_repetitions,
                "unit": definition.unit,
                **youtube_tutorial(definition.exercise_id, definition.name),
            }
            for definition in (by_id[exercise_id] for exercise_id in exercise_ids)
        ],
    }
