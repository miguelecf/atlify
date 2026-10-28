# Casos borde

`extract.py` usa heurísticas (regex), no un parser. Estas son las fallas conocidas, encontradas probándolo contra repos reales, y qué hacer en cada una. Ante la duda, manda el código: `grep` antes de afirmar.

## El esqueleto ve de menos

| Síntoma | Causa | Qué hacer |
|---|---|---|
| Rutas del backend sin el prefijo `/api` | El prefijo de `include_router(..., prefix=)` (FastAPI) o de `app.use('/api/x', router)` (Express) no se compone. | En `atlas.json` escribí la ruta completa, como la llama el cliente. `validate.py` y `build.py` comparan rutas por sufijo. |
| Backend Express o Fastify sin endpoints | `extract.py` solo detecta rutas de Spring y FastAPI. | `grep -rnE "\.(get|post|put|patch|delete)\(\s*['\"]/" <dir>` y armá la ruta completa con los `app.use`. |
| Frontend sin llamadas HTTP | El cliente es un SDK generado (`client.get({ url: "/api/..." })`, openapi-ts, orval) o un `fetch` envuelto. | Buscá las URLs en el SDK (`grep -rn "url: \"/api"`) y anotá en `frontend` la función del SDK y la pantalla que la usa. |
| La UI no aparece (FastAPI + Jinja + HTMX, Django) | Los templates HTML no se analizan. | Los templates son la nación frontend: citá el `.html` con `ancla` (el `hx-post="/..."` o el `action=`). En `archivos` usá `capa: "pagina"`. |
| Django sin endpoints ni modelos | `urls.py`, `views.py` y `models.Model` no se reconocen. | Las rutas salen de `urls.py`. Los modelos, de `class X(models.Model)`. |
| Tools MCP, colas o cron que no aparecen | Solo se detectan rutas HTTP. | Si son puntos de entrada importantes, tratalos como endpoints con `metodo` `"TOOL"`, `"JOB"` o `"CRON"`. |
| `Nodos:` vacío | Lenguaje no soportado (Go, Kotlin, Rust, C#). | Avisá al usuario. Si el repo es chico, armá el atlas a mano desde el código; si no, ofrecé solo el modo `--endpoint`. |

## El esqueleto ve de más o mal

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `service.py` o `repository.py` tipados como `modulo` | El tipo sale del nombre de la carpeta en plural (`services/`), no del archivo. | Poné la `capa` correcta en `archivos`. |
| `models.py` tipado como `config` | Está dentro de `core/`. | Ídem. |
| Un servicio aparece dos veces (`c:backend` y `c:svc.backend`) | Un servicio de compose con imagen propia y sin `build`. | Ignorá el duplicado. |
| 40 módulos planos en un contenedor | Cada carpeta hoja es un módulo. | Agrupá por funcionalidad con `etiqueta` en los endpoints. |

## PARA REVISAR

- **"solo coincide porque un literal cae en un parámetro":** la llamada pide `/pets/search`, pero el backend solo tiene `/pets/{pet_id}`. En FastAPI eso responde 422 (`"search"` no es un entero); en Express entra al handler con `id = "search"`. Casi siempre es una ruta que no existe: confirmalo y registralo en `llamadas_rotas` con su hallazgo.
- **"no lo llama ningún frontend":** puede ser código muerto, una API para terceros, o una llamada que el script no vio (SDK, URL armada en tiempo de ejecución). Buscá la ruta con `grep` antes de reportarla.
- Si la URL se arma en tiempo de ejecución (`${API_URL}${endpoint}`), el script no la juzga. Seguí la variable a mano.

## Impacto en el modo `--endpoint`

`build.py` busca en el código quién llama a cada función del recorrido y sube por quien la llama hasta 4 niveles, hasta llegar a un endpoint.

- **Ve:** llamadas directas por nombre (`book(`) o con el módulo delante (`pet_repository.get(`), y usos de clases (`Pet`).
- **No ve:** llamadas dinámicas (`getattr`, inyección de dependencias por tipo, métodos por interfaz), ni funciones con nombres genéricos (`get`, `save`) llamadas sin el módulo delante.
- Los ids de endpoints que vienen del esqueleto pueden no tener el prefijo (`GET /pets` en lugar de `GET /api/pets`).
- "Ninguna otra ruta llega a esta función" significa que no encontró llamadas, no que sea imposible. Decilo así en el reporte cuando el repo use inyección de dependencias.

## Repos grandes

- Más de 150 componentes o 40 endpoints: agrupá por funcionalidad y proponé hacerlas de a una, o `--endpoint`.
- Monorepos: un contenedor por app; las naciones del visor son las tres principales. Las demás apps van en `archivos` con su nación más cercana o `infra`.
- Archivos de más de 300 KB no se citan (suelen ser generados).
