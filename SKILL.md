---
name: atlas-codigo
description: >-
  Genera un atlas interactivo (HTML offline) de todo un repositorio: sistema →
  contenedores → módulos → clases → código, más flujos de casos de uso paso a
  paso. Usar SOLO cuando el usuario lo pida explícitamente ("atlas del código",
  "graficá todo el repo", "mapa del sistema", /atlas-codigo). Es costoso en
  tokens: no usar para explicar una función o un flujo puntual (eso es mentor).
license: MIT
metadata:
  author: Migue
  version: "0.1.0"
  tags: [atlas, arquitectura, visualizacion, aprendizaje]
disable-model-invocation: true
argument-hint: "[ruta-del-repo] [--solo-flujos | --actualizar]"
---

# Atlas del código

Genera `.atlas/atlas.html`: un mapa navegable del repo, de macro a micro (modelo C4), con explicaciones del **por qué** de cada pieza y flujos de casos de uso trazados por el código real.

La división del trabajo es la clave de esta skill:

| Quién | Hace | Archivo |
|---|---|---|
| `scripts/extract.py` | Lo mecánico: contenedores, paquetes, clases, métodos, endpoints, imports, llamadas HTTP front→back | `.atlas/skeleton.json` |
| **Vos (agente)** | Lo que requiere entender: resúmenes, decisiones, trade-offs, flujos, preguntas | `.atlas/enrich.json` |
| `scripts/build.py` | Une todo, copia los fragmentos de código reales, valida IDs y genera el HTML | `.atlas/atlas.html` |

Nunca escribas el HTML ni copies código a mano. Nunca reescribas lo que ya está en el esqueleto.

## Modos

- **Completo** (default, o sin `.atlas/enrich.json`): todo el flujo de abajo.
- **`--actualizar`** (existe `enrich.json`): corré `extract.py`, mirá el bloque `CAMBIOS` y actualizá solo esos nodos y los flujos que los atraviesan. Después, `build.py`.
- **`--solo-flujos`**: no toques resúmenes; agregá o corregí flujos.

## Flujo

Antes de empezar, avisale al usuario en una línea que es una tarea larga y que podés hacerla por contenedor si prefiere.

1. **Extraer.** `python <skill>/scripts/extract.py <repo>`. Leé el árbol que imprime; no leas `skeleton.json` entero (si necesitás un detalle, consultalo con `python -c` o `jq`).
2. **Corregir el esqueleto mentalmente.** Las heurísticas fallan: tipos mal detectados, relaciones de más o de menos. Lo corregís en `enrich.json` (`tipo`, `relaciones`, `quitar_relaciones`), no editando el esqueleto.
3. **Macro (sistema y contenedores).** Leé README, `docker-compose`, `pom.xml`/`package.json` y el entry point. Escribí `proyecto` y los `nodos` de cada contenedor.
4. **Módulos.** Por cada módulo, mirá las firmas (nombres, métodos, endpoints del árbol) y abrí solo los archivos necesarios para entender su rol. Resumen para **todos** los módulos; `porque` solo si hay una decisión real.
5. **Componentes clave.** Controllers, services, repositories, entities, páginas y clientes de API. DTOs, enums y utils, solo si son interesantes.
6. **Flujos (lo más valioso).** Elegí 2 a 4 casos de uso centrales del dominio (preguntale al usuario cuáles si está presente). Trazá cada uno **leyendo el código real**: UI → cliente HTTP → controller → service → repository → DB. Cada paso lleva `nodo`, `accion`, `desde`/`hasta` y `explicacion`. Entre 4 y 10 pasos por flujo.
7. **Nivel código.** Para los 5 a 10 métodos centrales de los flujos, agregá nodos `x:` en `nuevos`.
8. **Build.** `python <skill>/scripts/build.py <repo>`. Corregí **todos** los AVISOS y volvé a correrlo. Si quedan módulos sin resumen, completalos.
9. **Entregar.** Ruta del HTML, qué flujos incluiste y qué quedó sin explicar. Sugerí agregar `.atlas/` al `.gitignore` si no está, o versionar solo `enrich.json` si el usuario quiere conservar las explicaciones.

El esquema exacto de `enrich.json`, con ejemplo, está en `references/enrich.md`. Leelo antes del paso 3.

## Presupuesto de tokens

- Escribí `enrich.json` de forma incremental (un contenedor por vez, editando el archivo), no todo de una.
- No abras archivos completos para escribir un resumen si las firmas alcanzan.
- Los flujos sí requieren leer el código: ahí va el presupuesto.
- Para un repo grande (más de 150 componentes), proponé hacerlo por contenedor o empezar solo por los flujos.

## Reglas de contenido

- Explicá el **por qué**, no el qué obvio. "Es un controller REST" no aporta; "No tiene lógica: valida el DTO y delega, para que la regla de negocio sea testeable sin HTTP" sí.
- Si ves un problema de diseño (lógica de negocio en el controller, una entidad expuesta en la API, un N+1), decilo en el `porque` del nodo. El atlas también enseña lo que está mal.
- No inventes. Si no sabés por qué algo está así, omití el `porque` en vez de suponer.
- Español, directo, sin relleno. Las reglas de longitud están en `references/enrich.md`.
