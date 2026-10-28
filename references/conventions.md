# Convenciones de atlas.json

`atlas.json` es lo único que escribís. Nunca pongas código adentro: el código se cita con una referencia y `build.py` copia las líneas reales del repo.

El ejemplo completo y válido es `evals/fixtures/pet-care-api/atlas.json`. Copiá su forma.

## Referencias a código

Toda referencia lleva `archivo` (ruta relativa al repo) y una de estas dos formas de ubicar el código:

| Forma | Cuándo | Ejemplo |
|---|---|---|
| `simbolo` | Una función, método o clase. Es la preferida: si el código se mueve de línea, sigue funcionando. | `{ "archivo": "backend/app/routers/pets.py", "simbolo": "get_pet" }` |
| `ancla` + `lineas` | Algo que no es una función: una constante, un `useEffect`, una línea de config. `lineas` es cuántas líneas tomar después de la del ancla (0 = solo esa). | `{ "archivo": "frontend/src/pages/PetsPage.tsx", "ancla": "listPets().then", "lineas": 1 }` |

No uses `desde`/`hasta` fijos: se desfasan con el primer cambio, y `validate.py` lo marca como aviso.

## Esquema

```text
proyecto      nombre*, resumen, porque, rama, stack[{nombre, nacion}]
naciones[]    id* (frontend | backend | db), nombre, tipo, dir, resumen
archivos{}    "<ruta>": { nacion*, capa, rol }
endpoints[]   metodo*, ruta*, resumen*, tablas*[{tabla, op}], pasos*[], etiqueta, auth,
              explicacion, entrada (ref), respuestas[{codigo, desc}], frontend[ref], tests[ref]
  pasos[]     accion* + ref (código)  ó  accion* + tabla + op (base de datos); explicacion, pregunta
tablas[]      nombre*, modelo, ref del modelo, resumen, campos[{nombre, tipo, clave (pk|fk), ref, unico, sensible, desc}]
hallazgos[]   id*, severidad* (alta|media|baja), origen* (script|agente), categoria, titulo*,
              explicacion*, sugerencia*, ref*, endpoint, tabla
llamadas_rotas[]  metodo, ruta, ref, usadoEn[ref], coincide_con, hallazgo
```

`*` = obligatorio. `validate.py` rechaza claves que no estén acá: casi siempre es un error de tipeo.

Valores de `capa`: `pagina`, `cliente-api`, `rutas`, `router`, `service`, `repository`, `modelo`, `schema`, `seguridad`, `config`, `aplicacion`. Valores de `op`: `SELECT`, `INSERT`, `UPDATE`, `DELETE`.

## Un recorrido (`pasos`)

- Va del gesto del usuario a la base: pantalla → cliente API → router → service → repository → tabla. Entre 3 y 8 pasos.
- `accion` es lo que se ve en la caja: verbo y objeto, de 2 a 5 palabras, o el endpoint (`POST /api/appointments`).
- `explicacion`: qué pasa en este paso y **por qué así**, en 1 a 3 frases.
- `pregunta`: solo donde hay algo para razonar, como máximo en 1 de cada 3 pasos, y que no se responda con sí o no.
- El último paso es la tabla, con su `op`.

## Textos

| Campo | Regla |
|---|---|
| `resumen` | Qué hace, en 1 frase. Sin "Este endpoint se encarga de…". |
| `explicacion` | El mecanismo y la decisión. "Delega en el service" no aporta; "El router solo traduce SlotTaken a 409: la regla vive en el service y se testea sin HTTP" sí. |
| `rol` (archivo) | Para qué existe el archivo, en una línea. |
| `porque` | La decisión y su costo. Si no hay decisión interesante, omitilo. Nunca lo inventes. |
| hallazgo `titulo` | La consecuencia para el usuario o el sistema, no el nombre técnico: "Cualquiera puede cancelar cualquier turno", no "Falta auth en DELETE". |
| hallazgo `explicacion` | Cómo se produce, con el escenario concreto (quién hace qué y qué pasa). |
| hallazgo `sugerencia` | El arreglo mínimo, nombrando la función o el archivo donde va. |

Español, directo, sin relleno. Identificadores, rutas y código, tal cual.

## Qué buscar

Recorré cada endpoint con estas preguntas. Cada respuesta afirmativa, confirmada en el código, es un hallazgo.

**Seguridad**
- ¿El endpoint exige sesión? ¿Debería? Mirá especialmente los que modifican datos.
- ¿Verifica que el recurso sea del usuario, o alcanza con cambiar el id en la URL (IDOR)?
- ¿Devuelve entidades de la base tal cual, sin schema de salida? ¿Viaja algún campo sensible (hash, token, email ajeno)?
- ¿Hay secretos con valor por defecto o escritos en el código?

**Datos**
- ¿Hay "consultar y después escribir" sin una restricción en la base que lo respalde (condición de carrera)?
- ¿Las reglas de negocio están en la base (UNIQUE, FK, CHECK) o solo en el código?
- ¿Se borra lo que debería conservarse (historial), o al revés?

**Errores**
- ¿Qué excepciones puede lanzar el recorrido y cuáles se traducen a un código HTTP? Las que no, terminan en 500.
- ¿El frontend distingue los errores, o muestra el mismo mensaje para todo?

**Rendimiento**
- ¿Hay consultas dentro de bucles, o relaciones cargadas una por una (N+1)? Contá las consultas para un caso realista.
- ¿Se trae una lista entera para contarla o filtrarla en memoria?

**Diseño e integración**
- ¿Hay reglas de negocio en el router o en la pantalla, en lugar del service?
- ¿El frontend tiene datos copiados a mano que el backend ya expone?
- ¿Hay llamadas a rutas que no existen o endpoints que nadie usa? (PARA REVISAR ya te da candidatos.)
- ¿Hay funciones exportadas que nadie importa?

No conviertas en hallazgo una preferencia de estilo. Si dudás, que sea una `pregunta` en el paso.
