# Examples

The complete reference atlas is `evals/fixtures/pet-care-api/atlas.json`, over the repo in `evals/fixtures/pet-care-api/repo/`. Here are commented fragments to calibrate.

## One step

Weak: repeats what the code says.

```json
{ "archivo": "backend/app/routers/appointments.py", "simbolo": "create_appointment",
  "accion": "Creates the appointment", "explicacion": "This endpoint creates an appointment by calling the service." }
```

Good: explains the mechanism and the decision.

```json
{ "archivo": "backend/app/routers/appointments.py", "simbolo": "create_appointment",
  "accion": "Validates and delegates",
  "explicacion": "FastAPI validates the body against AppointmentCreate (if a field is missing, it returns 422 without running anything). The router only maps SlotTaken to 409.",
  "pregunta": "Why is it better for the router not to know how an occupied slot is decided?" }
```

## One finding

Weak: no scenario, no precise location, no fix.

```json
{ "id": "auth", "severidad": "alta", "origen": "agente", "titulo": "Security problem on DELETE",
  "explicacion": "Missing authentication.", "sugerencia": "Add auth.", "archivo": "backend/app/routers/appointments.py" }
```

Good: a title with the consequence, a concrete scenario, and the minimal fix where it belongs.

```json
{
  "id": "h-delete-sin-auth", "severidad": "alta", "origen": "agente", "categoria": "Seguridad",
  "titulo": "Anyone can cancel any appointment",
  "explicacion": "DELETE /api/appointments/{id} requires no session and never checks that the appointment belongs to the user. Someone with no account can cancel every appointment by trying ids from 1 up.",
  "sugerencia": "Add user: User = Depends(get_current_user) in the router and, in the service, verify a.pet.owner_id == user.id before cancelling.",
  "archivo": "backend/app/routers/appointments.py", "simbolo": "cancel_appointment",
  "endpoint": "DELETE /api/appointments/{appointment_id}"
}
```

## Findings that only appear reading with judgment

In the fixture, the script finds 3 things (the broken search and 2 unused endpoints). The rest requires following the walkthrough:

| Finding | How it is found |
|---|---|
| N+1 when listing appointments | Counting queries: a loop over pets, one appointment query per pet, and `a.pet`/`a.service` loaded one by one in `_to_out`. |
| Double booking by race | `exists_at` and then `add`, with no UNIQUE on `appointments`. Check the model to confirm the constraint is missing. |
| 500 with someone else's pet | `book` raises `PermissionError` and the router only catches `SlotTaken`. |
| Password hash exposed | `get_pet` returns `pet.owner` with no `response_model`, and `User` has `password_hash`. |
| Catalog copied in the frontend | `GET /api/services` exists and nobody uses it, and `NewAppointmentPage` has a hardcoded `SERVICES`. Two facts that only together explain the problem. |

## A suspicion that is not a finding

If `duration_min` exists but nothing uses it to avoid overlapping appointments, do not claim it as a bug without knowing the business rule. It goes as a question:

```json
"pregunta": "duration_min is not used when booking: can two 60-minute appointments start 30 minutes apart?"
```

## Final report

```text
Atlify: .atlify/atlas.html
Covers 9 of 9 endpoints and 4 tables.
Findings: 4 high, 5 medium, 2 low. The most severe:
- Anyone can cancel any appointment (appointments.py: cancel_appointment)
- The pet search calls a route that does not exist (pets.ts: searchPets)
- The pet detail returns the owner's password hash (pets.py: get_pet)
Unexplained: App.tsx (routes only). Suggestion: add .atlify/ to .gitignore or version only atlas.json.
```
