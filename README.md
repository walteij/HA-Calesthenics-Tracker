# Calisthenics Tracker for Home Assistant

Track your calisthenics workouts and body measurements from Home Assistant.
Calisthenics Tracker stores your data locally in Home Assistant and makes it
available as sensors for dashboards and automations.

## What can you do with it?

- Set up a personal profile with your start date, level, goal, and weekly
  targets.
- Start an A or B workout, record exercises and sets, and complete or cancel
  the workout.
- Get a suggested workout for core strength, conditioning, or supporting fat
  loss, based on your profile level. Choose the goal from a selector on your
  dashboard; no helpers or automations needed.
- For each exercise, record the variation you performed, reps per set, RIR
  (*repetitions in reserve*), pain score, and notes.
- Track body weight, waist circumference, resting heart rate, steps, sleep,
  calories, and protein.
- View workout frequency, training time, measurements, and exercise progress
  as Home Assistant sensors.
- See the next scheduled workout and whether it is session A or B.
- Follow progression or regression suggestions and beginner graduation
  readiness.

The integration does not create a long-term personalized training plan or
automatically assign exercises to session A or B. It can suggest an individual
workout based on your goal and profile level.

## Installation

### Install with HACS / MarketPlace

The marketplace (formerly known as HACS) is a community store for Home Assistant integrations; it is separate from the official Home Assistant add-on store. If **Calisthenics Tracker** is available in the HACS integration catalog, find it under **HACS → Integrations **and select **Download**.

If it is not listed in the catalog, add this GitHub repository as a custom repository:

1. In HACS, open **Integrations** and select the three-dot menu.
2. Select **Custom repositories**.
3. Enter `https://github.com/walteij/HA-Calesthenics-Tracker` and choose
   **Integration** as the category.
4. Add the repository, find **Calisthenics Tracker** in HACS, and select
   **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for
   **Calisthenics Tracker**, and complete setup.

Adding a custom repository only makes it available in your HACS instance; it
does not publish the integration to the default HACS catalog or an official
Home Assistant marketplace.

### Manual installation

1. In your Home Assistant configuration directory, create the folder
   `custom_components/calisthenics_tracker`.
2. Copy the contents of this repository's
   [`custom_components/calisthenics_tracker`](./custom_components/calisthenics_tracker)
   folder into it. For example, `manifest.json` should be located at
   `config/custom_components/calisthenics_tracker/manifest.json`.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **Calisthenics Tracker** and add it.
6. Fill in your profile. The integration supports one tracker profile at a
   time.

The profile cannot currently be edited in place. Removing and adding the
integration again also deletes your saved workouts and measurements, so only
do this if you intend to start over.

## Your first workout

The integration adds actions to Home Assistant. Find them under
**Developer tools → Actions** (called **Services** in some Home Assistant
versions).

### 1. Start a workout

Select `calisthenics_tracker.start_workout` and provide:

```yaml
session_type: A
```

Use `B` for session B. Only one workout can be active at a time. You can
optionally provide `started_at` as an ISO 8601 date and time with a timezone,
for example `2026-11-08T10:00:00+01:00`.

### 2. Log an exercise

While a workout is active, call `calisthenics_tracker.log_exercise`. For
example:

```yaml
exercise_id: beginner_push_up
variant: Strict push-up
sets:
  - 10
  - 9
  - 8
rir: 2
pain_score: 0
notes: Controlled tempo
```

`exercise_id` is the stable ID of an exercise in the catalog. The catalog
contains 30 exercises across beginner, intermediate, and advanced levels. You
can find the exercise IDs in
[`exercise_catalog.py`](./custom_components/calisthenics_tracker/exercise_catalog.py).
Enter the reps for each set under `sets`; every value must be positive. `rir`
is the number of additional reps you estimate you could have performed (0–5).
`pain_score` ranges from 0 to 10.

Logging the same exercise again during the same workout replaces its previous
log, so you can correct an entry without creating a duplicate. A pain score
of 4 or higher triggers a warning. This is not a medical assessment.

### Get a goal-focused workout suggestion

The easiest way is the **Calisthenics Workout Suggestion** device. Choose a
goal in `select.calisthenics_suggestion_focus`: core strength, conditioning,
or fat-loss support. The suggestion sensors update immediately with a routine
for the level in your profile. The integration remembers your choice after a
restart and updates the suggestion when your level changes. You do not need
helpers or automations.

| Entity                                          | What it shows                                        |
| ----------------------------------------------- | ---------------------------------------------------- |
| `select.calisthenics_suggestion_focus`          | The selected goal                                    |
| `sensor.calisthenics_suggestion_title`          | Name of the suggested workout                        |
| `sensor.calisthenics_suggestion_level`          | Level used for the suggestion                        |
| `sensor.calisthenics_suggestion_format`         | How to perform the circuit                           |
| `sensor.calisthenics_suggestion_note`           | An additional note, or empty when there is none      |
| `sensor.calisthenics_suggestion_exercise_count` | Number of suggested exercises                        |
| `sensor.calisthenics_suggestion_exercises`      | Number of exercises, with the full list as attribute |

The `exercises` attribute contains one entry per exercise with
`exercise_id`, `name`, `prescription`, `target_sets`, `minimum_repetitions`,
`maximum_repetitions`, `unit`, `tutorial_url`, and `tutorial_label`. For
example, use this in a template:

```jinja
{{ state_attr('sensor.calisthenics_suggestion_exercises', 'exercises')[0].name }}
```

To change the goal from an automation or script, use the standard select
action:

```yaml
action: select.select_option
target:
  entity_id: select.calisthenics_suggestion_focus
data:
  option: conditioning
```

You can also call `calisthenics_tracker.suggest_workout` directly and use the
result in the same automation or script:

```yaml
- action: calisthenics_tracker.suggest_workout
  data:
    focus: core_strength
  response_variable: suggestion
- action: notify.notify
  data:
    message: "{{ suggestion.title }}: {{ suggestion.exercises | length }} exercises"
```

The other options are `conditioning` and `fat_loss_support`. The action returns
the same routine, with exercise IDs and prescriptions, without changing the
selected goal. A suggestion does not start a workout or log exercises; start
an A or B workout separately, then log the exercises you performed. The
dashboard in the [`examples`](./examples) folder shows the goal selector and
the suggested workout.

#### Moving from helpers and automations

If you previously built suggestions with your own helpers, the integration
entities now replace them:

- Replace your `input_select` for the goal with
  `select.calisthenics_suggestion_focus`.
- Replace your `input_text` and `input_number` helpers with the
  `sensor.calisthenics_suggestion_*` sensors.
- Remove the automation that called `suggest_workout` when the goal changed;
  the integration now updates the sensors itself.

Update your dashboard cards and templates to the new entity IDs, then delete
the old helpers and automation.

The catalog includes extra core and conditioning exercises for these
suggestions. Conditioning can support energy expenditure, but does not
guarantee fat loss; nutrition and longer-term energy balance also matter.
Each suggested exercise includes a YouTube link. Selected exercises link to a
specific tutorial; the remaining exercises open YouTube results for an
exercise-specific form tutorial. Progress sensors also expose the link as the
`tutorial_url` attribute.

### 3. Complete the workout

Call `calisthenics_tracker.complete_workout`. The duration is calculated from
the start and completion times. You can optionally provide `notes` and
`completed_at`. Completed workouts count toward your weekly totals and
progress calculations.

If you do not want a workout to count, use
`calisthenics_tracker.cancel_workout`. The workout is retained with a cancelled
status but is not counted as completed. You can also use
`button.calisthenics_complete_workout` and
`button.calisthenics_cancel_workout`; these buttons perform the same actions
without additional input.

## Add body measurements

Use `calisthenics_tracker.add_body_measurement`. Provide one or more values; an
empty measurement or a note by itself is not saved. For example:

```yaml
weight_kg: 74.2
waist_cm: 81
steps: 9200
sleep_hours: 7.5
resting_heart_rate: 58
```

All measurement fields are optional, so you can record just your weight if
you prefer. Available fields:

| Field                  | Meaning                                             |
| ---------------------- | --------------------------------------------------- |
| `weight_kg`          | Body weight in kilograms                            |
| `waist_cm`           | Waist circumference in centimeters                  |
| `resting_heart_rate` | Resting heart rate in beats per minute              |
| `steps`              | Number of steps                                     |
| `sleep_hours`        | Sleep duration in hours                             |
| `calorie_intake`     | Calorie intake                                      |
| `protein_grams`      | Protein intake in grams                             |
| `measured_at`        | Optional measurement time as ISO 8601 with timezone |
| `notes`              | Optional note                                       |

## View your data

After setup, sensors named **Calisthenics ...** are available in Home
Assistant. Find them under **Settings → Devices & services → Calisthenics
Tracker → Entities**. The workout suggestion entities are grouped under the
**Calisthenics Workout Suggestion** device; see
[Get a goal-focused workout suggestion](#get-a-goal-focused-workout-suggestion).
Key sensors include:

| Sensor                                             | What it shows                                                         |
| -------------------------------------------------- | --------------------------------------------------------------------- |
| `sensor.calisthenics_active_workout`             | Whether a workout is active                                           |
| `sensor.calisthenics_next_workout`               | The next scheduled session, A or B                                    |
| `sensor.calisthenics_sessions_this_week`         | Completed workouts since Monday                                       |
| `sensor.calisthenics_training_minutes_this_week` | Training minutes since Monday                                         |
| `sensor.calisthenics_current_level`              | The level in your profile                                             |
| `sensor.calisthenics_current_week`               | Training week based on your profile start date                        |
| `sensor.calisthenics_latest_weight`              | Most recently recorded weight                                         |
| `sensor.calisthenics_weight_7_day_average`       | Average of measurements from today and the previous six calendar days |
| `sensor.calisthenics_weight_change_since_start`  | Latest weight minus first recorded weight                             |
| `sensor.calisthenics_latest_waist`               | Most recently recorded waist measurement                              |
| `sensor.calisthenics_average_daily_steps_7_days` | Average steps per measured day over the last seven calendar days      |
| `sensor.calisthenics_average_sleep_7_days`       | Average sleep per measured day over the last seven calendar days      |

One measurement day is enough to calculate a seven-day average; days without
measurements are ignored. If there are no usable measurements in the period,
the sensor is unavailable. Weekly workout totals start on Monday and include
completed workouts only.

Each catalog exercise has a progress sensor, for example
`sensor.calisthenics_progress_beginner_push_up`. Its state can be
`insufficient_data`, `progressing`, `maintaining`, `plateau`,
`progression_ready`, or `regression_recommended`. The sensor compares similar
completed workouts. Check its attributes for the variation and any related
regression or progression suggestion.

The `sensor.calisthenics_beginner_graduation_readiness` sensor reports
`not_ready`, `nearly_ready`, or `graduation_ready`. Only explicitly logged
strict variations are considered:

- 15 strict push-ups;
- 5 dead-hang pull-ups;
- 20 strict full-depth squats.

These are workout records and simple progress indicators, not medical advice
or a diagnosis.

## Dashboard and quick-entry scripts

The [`examples`](./examples) folder contains examples using standard Home
Assistant cards and scripts:

- [`calisthenics_dashboard.yaml`](./examples/calisthenics_dashboard.yaml):
  a dashboard with your active and next workouts, a workout suggestion by
  goal, weekly totals, and progress.
- [`calisthenics_tracker_scripts.yaml`](./examples/calisthenics_tracker_scripts.yaml):
  reusable scripts to start or complete a workout, log an exercise, and add a
  measurement. The `calisthenics_suggest_workout` script shows a suggestion
  as a notification; on the dashboard, the goal selector replaces it.

For example, you can include the scripts from your `configuration.yaml`:

```yaml
script: !include calisthenics_tracker_scripts.yaml
```

First copy the example file to your Home Assistant configuration directory,
then reload your scripts. If you already have a `script:` section, merge the
example scripts into your existing configuration. Exercise and measurement
actions require input; use the scripts or call the actions directly from the
Home Assistant interface.

To use the dashboard, create a dashboard with YAML configuration in Home
Assistant and copy in the contents of the dashboard example. Update entity IDs
if you have changed them.

## Privacy, backups, and removing the integration

Your profile, workouts, and measurements are stored locally by Home Assistant.
The integration does not use cloud services or send data to external services.
Include this data in your regular Home Assistant backups.

Removing the integration from **Settings → Devices & services** also deletes
the stored profile, workouts, and measurements. This cannot be undone. Remove
any copied dashboard and script configuration separately if you no longer
need it.
