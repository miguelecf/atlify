# Workflow por modo

`<skill>` es el directorio de este skill. Todo se escribe en `<repo>/.atlas/`.

## Modo completo

1. **Extraer.** `python3 <skill>/scripts/extract.py <repo>`. Del árbol que imprime, anotá:
   - contenedores (serán las naciones `frontend`, `backend`, `db`);
   - endpoints por archivo (`[N endpoints]`) y clientes HTTP (`[N llamadas HTTP]`);
   - la sección PARA REVISAR: candidatos a hallazgo con `origen: "script"`.
2. **Proyecto y naciones.** Leé README, compose, `package.json`/`pyproject.toml`/`pom.xml` y el entry point. Escribí `proyecto` y `naciones`. Corré `validate.py`.
3. **Por funcionalidad.** Agrupá los endpoints por lo que el negocio reconoce (turnos, mascotas, autenticación) y poné ese nombre en `etiqueta`. Casi siempre coincide con un router o controller, pero no siempre: un `routers/admin.py` puede mezclar varias, y una funcionalidad puede estar repartida en varios archivos. Para cada funcionalidad:
   1. Leé el handler y seguí las llamadas hasta la base: service, repository, modelo.
   2. Buscá quién lo llama en el frontend: el cliente API (`grep` de la ruta) y las pantallas que usan esa función.
   3. Escribí el endpoint completo: `resumen`, `explicacion`, `frontend`, `pasos` (de la pantalla a la tabla, de 3 a 8), `tablas`, `respuestas` y `entrada` si hay schema.
   4. Mientras leés, anotá hallazgos. Ahí está el valor: lo que solo se ve leyendo este código.
   5. Agregá a `archivos` cada archivo citado, con su `capa` y su `rol`.
   6. Corré `validate.py`.
4. **Tablas.** Una entrada por modelo: campos, claves, FK y el `porque` de lo que no es obvio (campos sensibles, restricciones que faltan).
5. **Hallazgos.** Revisá los de PARA REVISAR y confirmalos leyendo el código. Revisá la lista de `references/conventions.md` → "Qué buscar" sobre cada recorrido escrito.
6. **Cerrar.** `validate.py` sin errores y sin endpoints faltantes en la cobertura. Después, `build.py <repo>`.

Presupuesto: las firmas del árbol alcanzan para `rol` y `resumen`. Los recorridos y los hallazgos sí requieren leer el código: ahí va el gasto.

En un repo grande, hacé una funcionalidad por tanda. Antes de empezar, mostrá la lista (`Turnos: 6 endpoints`, `Pagos: 11 endpoints`…) y dejá que el usuario elija el orden. Cada tanda agrega sus endpoints al mismo `atlas.json`. `build.py` funciona con un atlas parcial, y el aviso de cobertura de `validate.py` muestra lo que falta.

## Modo un solo endpoint (`--endpoint "MÉTODO /ruta"`)

Para un fix chico en un repo grande. No escribas los demás endpoints: el impacto lo calcula `build.py` sobre el código.

1. `extract.py <repo>` igual que siempre (es barato y `build.py` usa el esqueleto para saber qué función atiende cada ruta).
2. Ubicá el endpoint en el árbol. Si la ruta no coincide exacta (los prefijos de `include_router` o `app.use` no siempre se ven), compará por sufijo y confirmá con el usuario si hay duda.
3. Escribí en `atlas.json` **solo**: `proyecto`, `naciones`, ese endpoint completo, sus `tablas`, los `archivos` citados y los hallazgos de su camino.
4. No escribas `tests` salvo que los encuentres vos: `build.py` busca los tests que llaman a las funciones del recorrido o piden la ruta.
5. `validate.py <repo> --endpoint "MÉTODO /ruta"` y luego `build.py <repo> --endpoint "MÉTODO /ruta"`.
6. En el reporte, copiá lo que imprime `build.py`: qué funciones comparte con otras rutas y cuántos tests encontró. Es lo que el usuario necesita antes de tocar el código.

## Modo actualizar (`--actualizar`)

1. `extract.py <repo>`: el bloque CAMBIOS lista los componentes nuevos, modificados y borrados.
2. `validate.py <repo>`: los errores de símbolos o anclas que ya no existen te dicen qué pasos se rompieron. Las referencias por símbolo siguen funcionando si el código solo se movió de línea.
3. Releé los recorridos que pasan por archivos modificados: un cambio puede volver falsa una explicación o resolver un hallazgo. Borrá los hallazgos resueltos.
4. Agregá los endpoints nuevos que marque el aviso de cobertura.
5. `build.py`. En el reporte: qué cambió en el atlas y qué hallazgos se resolvieron.

## Plan de arreglo (opcional)

Se ofrece al final de cualquier modo si hay hallazgos, y se escribe solo si el usuario acepta. Va en `.atlas/plan.md`, nunca en el repo. No arregles nada: el plan lo ejecuta el usuario con la herramienta o el agente que prefiera, así que cada tarea tiene que entenderse sin el atlas ni esta conversación.

- Una tarea por hallazgo (o por grupo, si comparten el arreglo), ordenadas por severidad. Si una depende de otra, decilo.
- Cada tarea: el id del hallazgo, qué está mal y el escenario concreto, los archivos y símbolos a tocar, el cambio mínimo, qué otras rutas comparten ese código (en `--endpoint`, sale de lo que imprimió `build.py`) y cómo verificar que quedó arreglado.
- Sin código completo: el arreglo se describe, no se escribe.

```markdown
# Plan de arreglo: pet-care-api

## 1. [alta] Cualquiera puede cancelar cualquier turno (h-delete-sin-auth)

- [ ] En `backend/app/routers/appointments.py`, `cancel_appointment`: exigir sesión con `Depends(get_current_user)`.
- [ ] En el service, verificar que el turno sea de una mascota del usuario antes de cancelar; si no, 404.
- Comparte código con: ninguna otra ruta usa `cancel`.
- Verificar: un DELETE sin token da 401, y con el token de otro dueño da 404.
```
