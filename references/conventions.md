# atlas.json conventions

`atlas.json` is the only thing you write. Never put code inside it: code is cited with a reference, and `build.py` copies the real lines from the repo.

The complete, valid example is `evals/fixtures/pet-care-api/atlas.json`. Copy its shape (structure and depth, not its language).

## Code references

Every reference carries `archivo` (path relative to the repo) and one of these two ways to locate the code:

| Form | When | Example |
|---|---|---|
| `simbolo` | A function, method or class. The preferred form: if the code moves lines, it still works. | `{ "archivo": "backend/app/routers/pets.py", "simbolo": "get_pet" }` |
| `ancla` + `lineas` | Something that is not a function: a constant, a `useEffect`, a config line. `lineas` is how many lines to take after the anchor's line (0 = just that one). | `{ "archivo": "frontend/src/pages/PetsPage.tsx", "ancla": "listPets().then", "lineas": 1 }` |

Do not use fixed `desde`/`hasta`: they drift with the first change, and `validate.py` flags them as a warning.

## Schema

```text
proyecto      nombre*, resumen, porque, rama, stack[{nombre, nacion}]
naciones[]    id* (frontend | backend | db), nombre, tipo, dir, resumen
archivos{}    "<ruta>": { nacion*, capa, rol }
endpoints[]   metodo*, ruta*, resumen*, tablas*[{tabla, op}], pasos*[], etiqueta, auth,
              explicacion, entrada (ref), respuestas[{codigo, desc}], frontend[ref], tests[ref]
  pasos[]     accion* + ref (code)  or  accion* + tabla + op (database); explicacion, pregunta
tablas[]      nombre*, modelo, ref of the model, resumen, campos[{nombre, tipo, clave (pk|fk), ref, unico, sensible, desc}]
              (in campos, `ref` is the FK destination as "table.field", e.g. "users.id"; it is not a code reference)
hallazgos[]   id*, severidad* (alta|media|baja), origen* (script|agente), categoria, titulo*,
              explicacion*, sugerencia*, ref*, endpoint, tabla
llamadas_rotas[]  metodo, ruta, ref, usadoEn[ref], coincide_con, hallazgo
```

`*` = required. `validate.py` rejects keys that are not in this list: it is almost always a typo.

`capa` values: `pagina`, `cliente-api`, `rutas`, `router`, `service`, `repository`, `modelo`, `schema`, `seguridad`, `config`, `aplicacion`. `op` values: `SELECT`, `INSERT`, `UPDATE`, `DELETE`.

## A walkthrough (`pasos`)

- It goes from the user's gesture to the database: screen → API client → router → service → repository → table. Between 3 and 8 steps.
- `accion` is what shows in the box: verb and object, 2 to 5 words, or the endpoint (`POST /api/appointments`).
- `explicacion`: what happens in this step and **why that way**, in 1 to 3 sentences.
- `pregunta`: only where there is something to reason about, at most in 1 of every 3 steps, and not answerable with yes or no.
- The last step is the table, with its `op`.

## Texts

| Field | Rule |
|---|---|
| `resumen` | What it does, in 1 sentence. No "This endpoint is in charge of…". |
| `explicacion` | The mechanism and the decision. "It delegates to the service" adds nothing; "The router only maps SlotTaken to 409: the rule lives in the service and is tested without HTTP" does. |
| `rol` (file) | Why the file exists, in one line. |
| `porque` | The decision and its cost. If there is no interesting decision, omit it. Never invent it. |
| finding `titulo` | The consequence for the user or the system, not the technical name: "Anyone can cancel any appointment", not "Missing auth on DELETE". |
| finding `explicacion` | How it happens, with the concrete scenario (who does what and what follows). |
| finding `sugerencia` | The minimal fix, naming the function or file where it goes. |

Direct, no filler. Identifiers, paths and code, exactly as they are.

## What to look for

Walk every endpoint with these questions. Every affirmative answer, confirmed in the code, is a finding.

**Security**
- Does the endpoint require a session? Should it? Look hard at the ones that modify data.
- Does it verify the resource belongs to the user, or is changing the id in the URL enough (IDOR)?
- Does it return database entities as-is, with no output schema? Does any sensitive field travel (hash, token, someone else's email)?
- Are there secrets with a default value or written in the code?

**Data**
- Is there a "read then write" with no database constraint backing it (race condition)?
- Are the business rules in the database (UNIQUE, FK, CHECK) or only in the code?
- Is something deleted that should be kept (history), or the other way around?

**Errors**
- Which exceptions can the walkthrough throw, and which ones are mapped to an HTTP code? The rest end up as 500.
- Does the frontend tell errors apart, or show the same message for everything?

**Performance**
- Queries inside loops, or relations loaded one by one (N+1)? Count the queries for a realistic case.
- Is a whole list fetched just to count or filter it in memory?

**Design and integration**
- Business rules in the router or the screen, instead of the service?
- Does the frontend have data copied by hand that the backend already exposes?
- Calls to routes that do not exist, or endpoints nobody uses? (TO REVIEW already gives candidates.)
- Exported functions nobody imports?

Do not turn a style preference into a finding. When in doubt, make it a `pregunta` in the step.
