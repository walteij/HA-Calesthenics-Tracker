"""Pure exercise progression and beginner graduation rules."""

import re
from dataclasses import dataclass
from enum import StrEnum

from .const import (
    GRADUATION_NEAR_READY_RATIO,
    PROGRESSION_MINIMUM_SESSIONS,
    PROGRESSION_PAIN_THRESHOLD,
    PROGRESSION_READY_CONSECUTIVE_SESSIONS,
    PROGRESSION_READY_MINIMUM_RIR,
    REGRESSION_MINIMUM_FAILURE_SESSIONS,
)
from .models import ExerciseDefinition, ExerciseLog, Workout


class ProgressionStatus(StrEnum):
    """Supported per-exercise progress states."""

    INSUFFICIENT_DATA = "insufficient_data"
    PROGRESSING = "progressing"
    MAINTAINING = "maintaining"
    PLATEAU = "plateau"
    PROGRESSION_READY = "progression_ready"
    REGRESSION_RECOMMENDED = "regression_recommended"


class GraduationStatus(StrEnum):
    """Beginner graduation state based only on verified strict variants."""

    NOT_READY = "not_ready"
    NEARLY_READY = "nearly_ready"
    GRADUATION_READY = "graduation_ready"


@dataclass(frozen=True, slots=True)
class ExerciseSessionSummary:
    """Bounded summary of one comparable completed performance."""

    completed_at: str
    total_repetitions: float
    set_count: int
    rir: int
    pain_score: int
    meets_minimum: bool | None
    reaches_maximum: bool | None


@dataclass(frozen=True, slots=True)
class ExerciseProgress:
    """Status, variant and at most three recent summaries for one exercise."""

    exercise_id: str
    status: ProgressionStatus
    variant: str | None
    recent_sessions: tuple[ExerciseSessionSummary, ...]


@dataclass(frozen=True, slots=True)
class GraduationReadiness:
    """Verified single-set scores against the three beginner criteria."""

    status: GraduationStatus
    push_ups: float | None
    dead_hang_pull_ups: float | None
    strict_full_depth_squats: float | None


def _session_summary(
    workout: Workout, log: ExerciseLog, definition: ExerciseDefinition
) -> ExerciseSessionSummary:
    target_sets = definition.target_sets
    prescribed_sets = log.sets[:target_sets]
    meets_minimum: bool | None = None
    reaches_maximum: bool | None = None
    if definition.minimum_repetitions is not None:
        meets_minimum = len(prescribed_sets) == target_sets and all(
            value >= definition.minimum_repetitions for value in prescribed_sets
        )
    if definition.maximum_repetitions is not None:
        reaches_maximum = len(prescribed_sets) == target_sets and all(
            value >= definition.maximum_repetitions for value in prescribed_sets
        )
    return ExerciseSessionSummary(
        completed_at=workout.completed_at.isoformat()
        if workout.completed_at is not None
        else "",
        total_repetitions=round(sum(prescribed_sets), 2),
        set_count=len(log.sets),
        rir=log.rir,
        pain_score=log.pain_score,
        meets_minimum=meets_minimum,
        reaches_maximum=reaches_maximum,
    )


def analyze_exercise_progress(
    exercise_id: str,
    definitions: tuple[ExerciseDefinition, ...],
    workouts: tuple[Workout, ...],
) -> ExerciseProgress:
    """Classify recent comparable logs without mutating tracker state."""
    definition = next(
        (item for item in definitions if item.exercise_id == exercise_id), None
    )
    logs = [
        (workout, log)
        for workout in workouts
        if workout.status == "completed" and workout.completed_at is not None
        for log in workout.exercises
        if log.exercise_id == exercise_id
    ]
    logs.sort(key=lambda pair: pair[0].completed_at, reverse=True)
    if definition is None or not logs:
        return ExerciseProgress(
            exercise_id, ProgressionStatus.INSUFFICIENT_DATA, None, ()
        )

    variant = logs[0][1].variant
    comparable = [
        (workout, log)
        for workout, log in logs
        if log.variant.casefold() == variant.casefold()
    ][:PROGRESSION_MINIMUM_SESSIONS]
    summaries = tuple(
        _session_summary(workout, log, definition) for workout, log in comparable
    )

    if comparable[0][1].pain_score >= PROGRESSION_PAIN_THRESHOLD:
        status = ProgressionStatus.REGRESSION_RECOMMENDED
    elif len(comparable) < PROGRESSION_MINIMUM_SESSIONS:
        status = ProgressionStatus.INSUFFICIENT_DATA
    elif (
        sum(summary.meets_minimum is False for summary in summaries)
        >= REGRESSION_MINIMUM_FAILURE_SESSIONS
    ):
        status = ProgressionStatus.REGRESSION_RECOMMENDED
    elif (
        definition.maximum_repetitions is not None
        and len(summaries) >= PROGRESSION_READY_CONSECUTIVE_SESSIONS
        and all(
            summary.reaches_maximum is True
            and summary.rir >= PROGRESSION_READY_MINIMUM_RIR
            and summary.pain_score < PROGRESSION_PAIN_THRESHOLD
            for summary in summaries[:PROGRESSION_READY_CONSECUTIVE_SESSIONS]
        )
    ):
        status = ProgressionStatus.PROGRESSION_READY
    elif (
        len(summaries) == PROGRESSION_MINIMUM_SESSIONS
        and len({(summary.total_repetitions, summary.rir) for summary in summaries})
        == 1
    ):
        status = ProgressionStatus.PLATEAU
    elif len(summaries) >= 2 and (
        summaries[0].total_repetitions > summaries[1].total_repetitions
        or (
            summaries[0].total_repetitions == summaries[1].total_repetitions
            and summaries[0].rir > summaries[1].rir
        )
    ):
        status = ProgressionStatus.PROGRESSING
    else:
        status = ProgressionStatus.MAINTAINING

    return ExerciseProgress(exercise_id, status, variant, summaries)


def _normalized_variant(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _has_phrase(value: str, *words: str) -> bool:
    return f" {' '.join(words)} " in f" {value} "


def _has_exercise_name(value: str, first: str, second: str) -> bool:
    return any(
        _has_phrase(value, *name.split())
        for name in (
            f"{first} {second}",
            f"{first} {second}s",
            f"{first}{second}",
            f"{first}{second}s",
        )
    )


def _verified_graduation_scores(
    workouts: tuple[Workout, ...],
) -> tuple[float | None, float | None, float | None]:
    scores: list[float | None] = [None, None, None]
    criteria = (
        ("beginner_push_up", "push_up"),
        ("intermediate_pull_up", "pull_up"),
        ("beginner_bodyweight_squat", "squat"),
    )
    for workout in workouts:
        if workout.status != "completed":
            continue
        for log in workout.exercises:
            for index, (exercise_id, kind) in enumerate(criteria):
                if log.exercise_id != exercise_id:
                    continue
                variant = _normalized_variant(log.variant)
                if kind == "push_up":
                    qualified = (
                        _has_phrase(variant, "strict")
                        and _has_exercise_name(variant, "push", "up")
                        and not any(
                            word in variant.split() for word in ("incline", "knee")
                        )
                    )
                elif kind == "pull_up":
                    qualified = _has_phrase(
                        variant, "dead", "hang"
                    ) and _has_exercise_name(variant, "pull", "up")
                else:
                    qualified = (
                        _has_phrase(variant, "strict")
                        and _has_phrase(variant, "full", "depth")
                        and any(word in variant.split() for word in ("squat", "squats"))
                    )
                if not qualified:
                    continue
                value = max(log.sets)
                if scores[index] is None or value > scores[index]:
                    scores[index] = float(value)
    return scores[0], scores[1], scores[2]


def beginner_graduation_readiness(
    workouts: tuple[Workout, ...],
) -> GraduationReadiness:
    """Evaluate only individually logged sets with explicitly qualified variants."""
    push_ups, pull_ups, squats = _verified_graduation_scores(workouts)
    scores = (push_ups, pull_ups, squats)
    targets = (15, 5, 20)
    if all(
        score is not None and score >= target
        for score, target in zip(scores, targets, strict=True)
    ):
        status = GraduationStatus.GRADUATION_READY
    elif all(
        score is not None and score >= target * GRADUATION_NEAR_READY_RATIO
        for score, target in zip(scores, targets, strict=True)
    ):
        status = GraduationStatus.NEARLY_READY
    else:
        status = GraduationStatus.NOT_READY
    return GraduationReadiness(status, push_ups, pull_ups, squats)
