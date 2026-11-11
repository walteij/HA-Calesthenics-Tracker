"""Constants for the local tracker."""

from homeassistant.const import Platform

DOMAIN = "calisthenics_tracker"
PLATFORMS = (Platform.SENSOR, Platform.BUTTON, Platform.SELECT)
STORAGE_VERSION = 4
DEFAULT_SESSIONS_PER_WEEK = 3
DEFAULT_DAILY_STEP_TARGET = 8000
LEVELS = ("beginner", "intermediate", "advanced")
SESSION_TYPES = ("A", "B")
SERVICE_START = "start_workout"
SERVICE_COMPLETE = "complete_workout"
SERVICE_CANCEL = "cancel_workout"
SERVICE_LOG_EXERCISE = "log_exercise"
SERVICE_ADD_BODY_MEASUREMENT = "add_body_measurement"
SERVICE_SUGGEST_WORKOUT = "suggest_workout"
WORKOUT_FOCI = ("core_strength", "conditioning", "fat_loss_support")
DEFAULT_SUGGESTION_FOCUS = "core_strength"
SUGGESTION_DEVICE_NAME = "Calisthenics Workout Suggestion"

PROGRESSION_MINIMUM_SESSIONS = 3
PROGRESSION_READY_CONSECUTIVE_SESSIONS = 2
PROGRESSION_READY_MINIMUM_RIR = 1
PROGRESSION_PAIN_THRESHOLD = 4
REGRESSION_MINIMUM_FAILURE_SESSIONS = 2
GRADUATION_NEAR_READY_RATIO = 0.8
