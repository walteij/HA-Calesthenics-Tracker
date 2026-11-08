# Calisthenics Tracker (Home Assistant custom integration)

Lokale custom integration voor Home Assistant met domein `calisthenics_tracker`.

## Huidige scope: fase 1 t/m 5

Deze fase levert:

- config flow voor één persoonlijk profiel;
- versioned opslag via `homeassistant.helpers.storage.Store`;
- actions:
  - `calisthenics_tracker.start_workout`
  - `calisthenics_tracker.complete_workout`
  - `calisthenics_tracker.cancel_workout`
  - `calisthenics_tracker.log_exercise`
  - `calisthenics_tracker.add_body_measurement`
- alle 22 oefendefinities uit de workbook, met stabiele IDs, niveaus, voorschriften,
  eenheden, tempo en beschikbare regressie-/progressievoorstellen;
- afzonderlijke setwaarden, RIR, pijnscore en notities per oefening;
- correctie van een oefening door een nieuwe log voor dezelfde `exercise_id`;
- sensors:
  - `sensor.calisthenics_active_workout`
  - `sensor.calisthenics_current_level`
  - `sensor.calisthenics_current_week`
  - `sensor.calisthenics_next_workout`
  - `sensor.calisthenics_sessions_this_week`
  - `sensor.calisthenics_training_minutes_this_week`
- buttons voor het afronden en annuleren van een actieve training;
- Engelse en Nederlandse vertalingen.
- lichaamsgewicht, middelomtrek, rusthartslag, stappen, slaap, calorie-inname,
  eiwitinname en lokale notities per lichaamsmeting;
- sensors voor laatste gewicht en middelomtrek, gewichtsverandering, het
  7-daags gemiddelde gewicht, gemiddelde stappen en gemiddelde slaap;
- voortgangssensor per catalogusoefening met maximaal drie recente sessies;
- beginner-graduatiesensor gebaseerd op expliciet gelabelde strikte varianten;
- volgende-training-sensor volgens het A/B weekschema;
- voorbeeld-Lovelace-dashboard met standaardkaarten en parameterized scripts.

## Installatie

1. Plaats de map `custom_components/calisthenics_tracker/` in de Home Assistant-configuratiemap.
2. Herstart Home Assistant.
3. Ga naar **Settings → Devices & services → Add integration**.
4. Zoek op **Calisthenics Tracker**.

## Configuratie

De config flow vraagt:

- profielnaam;
- startdatum;
- huidig niveau;
- doel;
- trainingen per week;
- dagelijks stappendoel.

## Actions

### `calisthenics_tracker.start_workout`

Verplicht:
- `session_type`: `A` of `B`.

Optioneel:
- `started_at`: timezone-aware ISO 8601.

### `calisthenics_tracker.complete_workout`

Optioneel:
- `completed_at`: timezone-aware ISO 8601.
- `notes`: tekst.

### `calisthenics_tracker.cancel_workout`

Annuleert de actieve training en bewaart die met status `cancelled`; deze telt
niet mee voor voltooide trainingen of progressieberekeningen. Er volgt een
duidelijke foutmelding als er geen actieve training is.

### `calisthenics_tracker.log_exercise`

Vereist een actieve training:

- `exercise_id`: ID uit de catalogus hieronder;
- `variant`: daadwerkelijk uitgevoerde variant;
- `sets`: niet-lege lijst met één positief getal per set;
- `rir`: geheel getal van 0 tot en met 5;
- `pain_score`: geheel getal van 0 tot en met 10.

Optioneel:

- `notes`: lokale notitie.

Een tweede action call voor dezelfde `exercise_id` **vervangt** de eerdere log in
dezelfde actieve training; er ontstaat geen dubbele oefenregistratie. Bij een
pijnscore van 4 of hoger geeft de action een waarschuwing (`pain_warning: true`)
en wordt een algemene waarschuwing gelogd. De integration doet geen diagnose of
automatische oefenvoorschriften.

De workbook bevat geen A/B-oefenverdeling. Daarom zijn de definities niet aan A
of B toegewezen en kan dezelfde oefening in beide sessies worden gelogd.

### Oefeningencatalogus

| Niveau | Exercise ID |
|---|---|
| Beginner | `beginner_push_up`, `beginner_inverted_row_band_pull_up`, `beginner_bodyweight_squat`, `beginner_walking_lunge`, `beginner_plank`, `beginner_glute_bridge` |
| Intermediate | `intermediate_feet_elevated_push_up`, `intermediate_parallel_bar_dip`, `intermediate_pike_push_up`, `intermediate_pull_up`, `intermediate_chin_up`, `intermediate_feet_elevated_inverted_row`, `intermediate_bulgarian_split_squat`, `intermediate_pistol_squat_negative`, `intermediate_assisted_nordic_curl` |
| Advanced | `advanced_muscle_up_progression`, `advanced_one_arm_pull_up_progression`, `advanced_front_lever_progression`, `advanced_pistol_squat_progression`, `advanced_weighted_dip`, `advanced_weighted_pull_up`, `advanced_weighted_pistol_squat` |

De volledige namen en voorschriften staan in de lokaal opgeslagen `exercise_definitions`
en de typed catalogus in `custom_components/calisthenics_tracker/exercise_catalog.py`.

### `calisthenics_tracker.add_body_measurement`

Voeg een meting toe met één of meer van deze optionele velden:

- `measured_at`: optionele timezone-aware ISO 8601-tijd; standaard het huidige tijdstip;
- `weight_kg`: lichaamsgewicht, groter dan 0 en maximaal 500 kg;
- `waist_cm`: middelomtrek, groter dan 0 en maximaal 300 cm;
- `resting_heart_rate`: geheel getal van 1 tot en met 300 bpm;
- `steps`: niet-negatief geheel getal;
- `sleep_hours`: getal van 0 tot en met 24 uur;
- `calorie_intake` en `protein_grams`: eindige, niet-negatieve getallen;
- `notes`: optionele lokale notitie.

Minimaal één meetwaarde is vereist; een notitie alleen is niet voldoende. Elke
meting krijgt een stabiele UUID en wordt met de overige gegevens lokaal in Home
Assistant Storage bewaard. Er worden geen gezondheidsgegevens naar buiten
verstuurd.

De gewichts- en middelomtreksensoren tonen de meest recente meting van het
betreffende veld. De gewichtsverandering is `laatste gewicht - eerste gewicht`;
een negatieve waarde betekent gewichtsverlies. De sensoren voor het 7-daags
gemiddelde gebruiken de lokale kalenderdagen van vandaag en de zes voorafgaande
dagen. Per gemeten dag telt de laatste waarde mee; dagen zonder meting worden
genegeerd. Eén meetdag is voldoende om een gemiddelde te tonen; zonder metingen
in de periode is de sensor `unavailable`. Dit geldt ook voor gemiddelde stappen
en slaap.

## Progressie en beginner-graduatie

Per oefening verschijnt een sensor zoals
`sensor.calisthenics_progress_beginner_push_up`. De state is een van:
`insufficient_data`, `progressing`, `maintaining`, `plateau`,
`progression_ready` of `regression_recommended`. De attributen bevatten de
variant, voorschriften, maximaal drie recente sessies en waar van toepassing de
workbook-regressie of -progressie.

De engine vergelijkt maximaal de drie meest recente voltooide logs van dezelfde
oefening en variant. Minder dan drie vergelijkbare logs geeft
`insufficient_data`, behalve een recente pijnscore vanaf 4; die geeft direct
`regression_recommended`. Ook twee of meer recente sessies waarbij minstens een
voorgeschreven set onder het minimum blijft, adviseren regressie.
`progression_ready` vereist dat alle voorgeschreven sets in twee opeenvolgende
trainingen de maximumreps halen, RIR minimaal 1 is en de pijnscore lager dan 4
blijft. `plateau` vereist drie opeenvolgende vergelijkbare sessies met exact
gelijke totale herhalingen en RIR; een enkele slechte training is dus geen
plateau. Een stijging in totale herhalingen of RIR ten opzichte van de vorige
vergelijkbare training geldt als `progressing`; overige uitkomsten zijn
`maintaining`.

De sensor `sensor.calisthenics_beginner_graduation_readiness` toont
`not_ready`, `nearly_ready` of `graduation_ready`. Alleen sets uit voltooide
workouts met expliciete variantlabels tellen mee: `strict push-up`,
`dead-hang pull-up` en `strict full-depth squat` (ook spatie- en meervoudvormen
worden herkend). Voor elke beweging telt de hoogste afzonderlijke set, nooit
het opgetelde trainingsvolume. De doelen zijn respectievelijk 15, 5 en 20
herhalingen. `nearly_ready` vereist dat alle drie geverifieerde scores ten
minste 80% van hun doel halen; zonder gekwalificeerde score voor alle drie
blijft de status `not_ready`. De sensorattributen tonen gevonden scores en
doelen, niet de workoutgeschiedenis.

Progressie- en regressie-uitkomsten zijn trainingssuggesties, geen diagnoses.
Bij een hoge pijnscore wordt geen zwaardere oefening voorgesteld.

## Volgende training

De sensor `sensor.calisthenics_next_workout` toont sessie A of B en geeft de
geplande lokale datum als `scheduled_date`-attribuut. Het standaardschema is
woensdag A, vrijdag B en zondag afwisselend op basis van de laatst voltooide
zondagtraining (A als er nog geen zondagtraining is geregistreerd). Maandag,
dinsdag, donderdag en zaterdag zijn rust- of wandeldagen. Een al voltooide
training op de huidige geplande dag wordt overgeslagen.

`sensor.calisthenics_current_week` toont de trainingsweek sinds de ingestelde
startdatum. De startdatum is week 1; elke daaropvolgende periode van zeven
lokale kalenderdagen verhoogt het weeknummer. Voor een toekomstige startdatum
is de sensor `unavailable`. `sensor.calisthenics_current_level` toont het
niveau uit het profiel.

De buttons `button.calisthenics_complete_workout` en
`button.calisthenics_cancel_workout` voeren dezelfde acties uit zonder
parameters. De annuleerknop bewaart de registratie als `cancelled`.

## Lovelace-dashboard en scripts

De voorbeelden staan in `examples/`:

- `calisthenics_dashboard.yaml`: dashboard met Tile-, Entities-,
  Statistics Graph-, History Graph- en Markdown-kaarten;
- `calisthenics_tracker_scripts.yaml`: scripts voor het starten en afronden
  van trainingen, het loggen van een oefening en het toevoegen van
  lichaamsmetingen.

Voor de scripts:

1. Kopieer `examples/calisthenics_tracker_scripts.yaml` naar de hoofdmap van
   je Home Assistant-configuratie.
2. Voeg `script: !include calisthenics_tracker_scripts.yaml` toe aan
   `configuration.yaml`. Als daar al een `script:`-sectie staat, voeg de
   scriptdefinities dan op de bestaande manier samen.
3. Herlaad de scripts via **Developer tools → YAML → Reload scripts**, of
   herstart Home Assistant.

Daarna zijn onder andere `script.calisthenics_start_workout`,
`script.calisthenics_complete_workout`, `script.calisthenics_log_exercise` en
`script.calisthenics_add_body_measurement` beschikbaar. De oefenset-input is
een lijst positieve getallen, bijvoorbeeld `[10, 9, 8]`. De meetwaarden-script
accepteert een object met een of meer velden; minimaal één meetwaarde is
vereist. Alle scripts roepen de lokale integration-actions aan.

Voor het dashboard:

1. Open `examples/calisthenics_dashboard.yaml` en kopieer de YAML-inhoud.
2. Ga in Home Assistant naar **Settings → Dashboards → Add dashboard** en
   maak een dashboard met YAML-configuratie.
3. Plak de inhoud en sla het dashboard op.

Het voorbeeld gebruikt uitsluitend standaard Home Assistant-kaarten. Pas de
entiteiten aan als je de standaard entity IDs via de entiteitsinstellingen
hebt gewijzigd.

## Lokale opslag

Gegevens worden lokaal opgeslagen in Home Assistant storage met schema:

```json
{
  "schema_version": 3,
  "profile": {},
  "exercise_definitions": [],
  "workouts": [],
  "body_measurements": []
}
```

De eerste initialisatie vult `exercise_definitions` met de 22 catalogusitems.
Versies 1 en 2 worden automatisch naar versie 3 gemigreerd; bestaande workouts
en profielgegevens blijven behouden.

## Ontwikkelen en testen

Dit project gebruikt Python 3.14.2+ en Home Assistant 2026.11.0.

```powershell
uv sync
uv run ruff check .
```

On Windows PowerShell, run tests with:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
uv run python -m pytest -p pytest_asyncio.plugin
```

The plugin setting avoids conflicts when unrelated pytest plugins are
installed in the Python environment.

## Verwijderen

Verwijder de integratie via **Settings → Devices & services → Calisthenics
Tracker → Delete**. Bij het verwijderen van de config entry worden het lokale
profiel, de trainingen, lichaamsmetingen en de oefeningencatalogus uit Home
Assistant Storage verwijderd. Dit kan niet ongedaan worden gemaakt. Verwijder
eventueel ook de gekopieerde dashboard- en scriptconfiguratie uit je Home
Assistant-configuratie.
