# Edge cases

`extract.py` uses heuristics (regex), not a parser. These are the known misses, found testing against real repos, and what to do about each one. When in doubt, the code wins: `grep` before asserting.

## The skeleton under-detects

| Symptom | Cause | What to do |
|---|---|---|
| Backend routes without the `/api` prefix | The prefix of `include_router(..., prefix=)` (FastAPI) or `app.use('/api/x', router)` (Express) is not composed. | Write the full route in `atlas.json`, as the client calls it. `validate.py` and `build.py` compare routes by suffix, and the `--endpoint` argument accepts either form. |
| Express or Fastify backend with no endpoints | `extract.py` only detects Spring and FastAPI routes. | `grep -rnE "\.(get|post|put|patch|delete)\(\s*['\"]/" <dir>` and compose the full route with the `app.use`s. |
| Frontend with no HTTP calls | The client is a generated SDK (`client.get({ url: "/api/..." })`, openapi-ts, orval) or a wrapped `fetch`. | Find the URLs in the SDK (`grep -rn "url: \"/api"`) and note in `frontend` the SDK function and the screen that uses it. |
| The UI does not show up (FastAPI + Jinja + HTMX, Django) | HTML templates are not analyzed. | The templates are the frontend nacion: quote the `.html` with `ancla` (the `hx-post="/..."` or the `action=`). In `archivos` use `capa: "pagina"`. |
| Django with no endpoints or models | `urls.py`, `views.py` and `models.Model` are not recognized. | Routes come from `urls.py`. Models, from `class X(models.Model)`. |
| MCP tools, queues or cron jobs missing | Only HTTP routes are detected. | If they are important entry points, treat them as endpoints with `metodo` `"TOOL"`, `"JOB"` or `"CRON"`. |
| `Nodes:` empty | Unsupported language (Go, Kotlin, Rust, C#). | Tell the user. If the repo is small, build the atlas by hand from the code; otherwise offer only `--endpoint` mode. |

## The skeleton over-detects or gets it wrong

| Symptom | Cause | What to do |
|---|---|---|
| `service.py` or `repository.py` typed as `modulo` | The type comes from the plural folder name (`services/`), not the file. | Put the correct `capa` in `archivos`. |
| `models.py` typed as `config` | It sits inside `core/`. | Same. |
| One service appears twice (`c:backend` and `c:svc.backend`) | A compose service with its own image and no `build`. | Ignore the duplicate. |
| 40 flat modules in one container | Every leaf folder is a module. | Group by functionality with `etiqueta` in the endpoints. |

## TO REVIEW

- **"only matches because a literal falls into a parameter":** the call asks for `/pets/search`, but the backend only has `/pets/{pet_id}`. In FastAPI that answers 422 (`"search"` is not an integer); in Express it enters the handler with `id = "search"`. It is almost always a route that does not exist: confirm it and record it in `llamadas_rotas` with its finding.
- **"is called by no frontend":** it may be dead code, an API for third parties, or a call the script did not see (SDK, URL assembled at runtime). `grep` the route before reporting it.
- If the URL is assembled at runtime (`${API_URL}${endpoint}`), the script does not judge it. Follow the variable by hand.

## Impact in `--endpoint` mode

`build.py` searches the code for who calls every function of the walkthrough and climbs through callers up to 4 levels, until it reaches an endpoint.

- **Sees:** direct calls by name (`book(`) or with the module in front (`pet_repository.get(`), and class usages (`Pet`).
- **Does not see:** dynamic calls (`getattr`, dependency injection by type, methods through an interface), or functions with generic names (`get`, `save`) called without the module in front.
- The endpoint ids coming from the skeleton may lack the prefix (`GET /pets` instead of `GET /api/pets`). The CLI matches by suffix, so either form works.
- "No other route reaches this function" means it found no calls, not that it is impossible. Say it that way in the report when the repo uses dependency injection.

## Large repos

- More than 150 components or 40 endpoints: group by functionality and propose doing them one at a time, or `--endpoint`.
- Monorepos: one container per app; the viewer's naciones are the three main ones. The other apps go in `archivos` with their closest nacion or `infra`.
- Files larger than 300 KB are not quoted (they are usually generated).
