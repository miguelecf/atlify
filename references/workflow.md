# Workflow by mode

`<skill>` is the directory of this skill. Everything is written into `<repo>/.atlify/`. All commands are `python3 <skill>/scripts/atlify.py <subcommand>`; below they are abbreviated `extract`, `validate` and `build`.

## Full mode

1. **Extract.** `atlify.py extract <repo>`. From the tree it prints, note:
   - containers (they become the `frontend`, `backend`, `db` naciones);
   - endpoints per file (`[N endpoints]`) and HTTP clients (`[N HTTP calls]`);
   - the TO REVIEW section: finding candidates with `origen: "script"`.
2. **Project and naciones.** Read the README, compose files, `package.json`/`pyproject.toml`/`pom.xml` and the entry point. Write `proyecto` and `naciones`. Run `atlify.py validate <repo>`.
3. **Per functionality.** Group the endpoints by what the business recognizes (appointments, pets, authentication) and put that name in `etiqueta`. It usually matches a router or controller, but not always: a `routers/admin.py` may mix several, and one functionality may be spread across several files. For each functionality:
   1. Read the handler and follow the calls down to the base: service, repository, model.
   2. Find who calls it in the frontend: the API client (`grep` the route) and the screens that use that function.
   3. Write the complete endpoint: `resumen`, `explicacion`, `frontend`, `pasos` (from the screen to the table, 3 to 8), `tablas`, `respuestas` and `entrada` if there is a schema.
   4. While reading, note findings. That is where the value is: what only surfaces reading this code.
   5. Add every quoted file to `archivos`, with its `capa` and `rol`.
   6. Run `atlify.py validate <repo>`.
4. **Tables.** One entry per model: fields, keys, FKs and the `porque` of what is not obvious (sensitive fields, missing constraints).
5. **Findings.** Review the TO REVIEW ones and confirm them by reading the code. Run the "What to look for" list from `references/conventions.md` over every walkthrough you wrote.
6. **Close.** `atlify.py validate <repo>` with no errors and no missing endpoints in coverage. Then `atlify.py build <repo>`.

Budget: the signatures in the tree are enough for `rol` and `resumen`. The walkthroughs and findings do require reading the code: that is where the cost goes.

In a large repo, do one functionality per batch. Before starting, show the list (`Appointments: 6 endpoints`, `Payments: 11 endpoints`…) and let the user pick the order. Each batch adds its endpoints to the same `atlas.json`. `atlify.py build <repo>` works with a partial atlas, and validate's coverage warning shows what is missing.

## Single-endpoint mode (`--endpoint "METHOD /path"`)

For a small fix in a large repo. Do not write the other endpoints: the blast radius is computed by `build` over the code.

1. `atlify.py extract <repo> --routes`: the endpoint inventory without the tree (saves tokens). `build` uses the skeleton to know which function serves each route.
2. Locate the endpoint in the inventory. If the route does not match exactly (the prefixes of `include_router` or `app.use` are not always visible), compare by suffix; the CLI matches by suffix too, so both forms work. If several candidates remain, ask the user.
3. Write into `atlas.json` **only**: `proyecto`, `naciones`, that one complete endpoint, its `tablas`, the quoted `archivos` and the findings on its path.
4. Do not write `tests` unless you found them yourself: `build` looks for the tests that call the functions of the walkthrough or request the route. An empty list `[]` is treated as "not written" and discovered the same way.
5. `atlify.py validate <repo> --endpoint "METHOD /path"` and then `atlify.py build <repo> --endpoint "METHOD /path"`.
6. In the report, copy what `build` prints: which functions are shared with other routes and how many tests it found. That is what the user needs before touching the code.

## Update mode (`--actualizar`)

`atlify.py --actualizar <repo>` (same as running extract again; add `--routes` when the atlas is complete and only the changes matter):

1. `atlify.py extract <repo>`: the CHANGES block lists the added, modified and deleted components.
2. `atlify.py validate <repo>`: errors about symbols or anchors that no longer exist tell you which steps broke. Symbol references keep working if the code only moved lines.
3. Re-read the walkthroughs that pass through modified files: a change can make an explanation false or resolve a finding. Delete the resolved findings.
4. Add the new endpoints marked by the coverage warning.
5. `atlify.py build <repo>`. In the report: what changed in the atlas and which findings were resolved.

## Fix plan (optional)

Offered at the end of any mode when there are findings, and written only if the user accepts. It goes in `.atlify/plan.md`, never in the repo. Fix nothing: the plan is executed by the user with the tool or agent they prefer, so every task must be understandable without the atlas and without this conversation.

- One task per finding (or per group, if they share the fix), ordered by severity. If one depends on another, say so.
- Each task: the finding id, what is wrong and the concrete scenario, the files and symbols to touch, the minimal change, which other routes share that code (in `--endpoint`, from what `build` printed) and how to verify it is fixed.
- No complete code: the fix is described, not written.

```markdown
# Fix plan: pet-care-api

## 1. [alta] Anyone can cancel any appointment (h-delete-sin-auth)

- [ ] In `backend/app/routers/appointments.py`, `cancel_appointment`: require a session with `Depends(get_current_user)`.
- [ ] In the service, verify the appointment belongs to a pet of the user before cancelling; otherwise 404.
- Shared code with: no other route uses `cancel`.
- Verify: a DELETE without a token returns 401, and with another owner's token returns 404.
```
