# Why the User Is Not Yet Satisfied

## Core mismatch

The early implementation treated object recognition as the definition of an event. That did not match the user's actual expectation: "show me what happened" even when a compact model is uncertain. A visible person was recognized at only about 29% confidence while the initial threshold was 55%, so no image appeared. The system was technically running but failed the user's practical test.

## Specific causes

### Overly strict confidence default

The first live person was clearly visible but fell below the generic confidence setting. The threshold was not calibrated against the actual elevated doorway view before claiming readiness.

### Incorrect cooldown semantics

The first design used a 30-second per-label cooldown. A person leaving and returning within that interval could be merged or suppressed. The user reasonably expected each appearance to be represented. This was replaced with presence/absence re-arming.

### Single-image interpretation was too narrow

One snapshot cannot reliably communicate a short action. The user wanted evidence of movement and proposed capturing stills first, then grouping nearby stills into a GIF. That expectation should have been captured earlier as an activity-burst requirement.

### Premature completion language

Some responses described components as working after unit or host-local checks, before the real phone-facing behavior had passed an end-to-end test. "Implemented" and "verified in real use" were not separated clearly enough.

### Infrastructure detour

The first attempt used Frigate under Docker/WSL. Although Frigate matched the original requirement, the laptop's approximately 3.5 GiB WSL allocation and existing containers caused WSL restarts. This consumed time before the resource constraint drove the project toward a native Windows design.

### Unnecessary credential friction

The application initially expected a private launcher variable instead of using the obvious `.env` workflow. The user had to explicitly request a `.env` file.

### Awkward initial project location

The project was initially created inside a generated Codex output directory rather than a normal Documents folder. It was later moved to `C:\Users\Konda\Documents\EZVIZ-Event-Gallery`.

## What must change in the working approach

- Validate behavior with the actual camera view before declaring a feature working.
- Use general activity capture as the safety net; treat AI labels as enrichment.
- State measured evidence: event count, timestamp, media file, and phone-visible result.
- Separate "coded," "locally tested," and "accepted by the user."
- Prefer simple file/SQLite solutions and avoid adding services.
- Tune thresholds from captured samples, not generic defaults.
- Make changes against explicit user scenarios: leave, return, stand still, shadows, clothes moving, and cat movement.
- Do not call the first version complete until startup recovery, resource limits, and remote phone access are tested.

## Definition of regained confidence

The user should be able to repeat ordinary doorway activity and consistently see useful, distinct gallery cards without prompting manual debugging. The feed should explain the event visually, remain fast on the phone, avoid noise when nothing relevant happens, and continue working after the laptop or camera temporarily disconnects.

