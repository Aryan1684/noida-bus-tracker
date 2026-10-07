# Design Principles

## Core promise

"Here's where the bus is, and here's how much you should believe it."

## Dependency chain

Data Trust → Position Trust → User Trust → ETA Quality → Product Features → Scale

## Pipeline order

Raw GPS → Timestamp → Coordinates → Dedup → Out-of-order → Speed → Canonical History → Route Match → Confidence → Estimated Position → ETA → Display

Each stage protects the stage after it. A later stage must never treat rejected raw data as trustworthy input.

Every position must either pass forward or be rejected with a machine-readable reason. Reordering the pipeline requires revisiting the dependencies below it.

## Rules

1. Never skip a layer to build features faster.
2. Confidence uses validated data, never raw GPS.
3. Display position is for the map only, never for computation.
4. Confidence scoring starts as deterministic rules with reason traces.
5. Infrastructure such as Redis, queues, WebSocket, or Kafka follows measured need.
6. Every bus position has a traceable pipeline state.
7. Rejection reasons are retained long enough to distinguish upstream failures from pipeline failures.
8. Upstream identity is recorded separately from internal identity so identity instability can be detected before an identity system is justified.

## Milestones

### Milestone 1: Data Trust

Done when deliberate corruption can be injected and the pipeline reports the exact stage and reason that rejected it.

### Milestone 2: Position Trust

Done when live bus positions are route-matched, route progress is measured, off-route distance is surfaced, and confidence reasons are emitted.

### Milestone 3: User Trust

Done when the UI distinguishes Live, Estimated, and Last Known and exposes freshness and confidence reasons.

### Milestone 4: ETA Quality

Done when ETA uses segment-level historical traversal times and returns an ETA range with confidence.

## Complexity rule

Use one FastAPI app, one PostgreSQL database, one collector process, one clearly ordered pipeline, one deterministic confidence evaluator, and one frontend until measurements prove additional infrastructure is needed.
