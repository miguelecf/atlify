# enrich.json: esquema

Es lo único que escribís vos. Todo lo mecánico (nodos, métodos, endpoints, imports) ya está en `skeleton.json`, generado por `extract.py`. Acá solo va lo que requiere entender el código.

**Nunca escribas código en este archivo.** Para mostrar código, indicá `archivo` + `desde`/`hasta` y `build.py` copia las líneas reales del repo.

```json
{
  "proyecto": {
    "nombre": "Gestión de Eventos UNLa",
    "resumen": "Qué hace el sistema y para quién, en 1–2 frases.",
    "porque": "Decisión de arquitectura principal y su trade-off.",
    "pregunta": "Opcional: pregunta para razonar a nivel sistema."
  },

  "nodos": {
    "c:backend": {
      "resumen": "API REST en Spring Boot que expone la gestión de eventos e inscripciones.",
      "porque": "Monolito en capas: simple de desplegar para el alcance del TFI; el coste es que todo escala junto."
    },
    "m:backend:service": {
      "resumen": "Reglas de negocio: cupos, estados del evento, validaciones.",
      "pregunta": "¿Qué regla de negocio está hoy en un controller y debería estar acá?"
    },
    "k:backend/src/main/java/ar/edu/unla/eventos/service/InscripcionService.java": {
      "resumen": "Inscribe usuarios controlando el cupo.",
      "porque": "La verificación de cupo y el insert van en la misma transacción para no sobrevender.",
      "desde": 24, "hasta": 41
    }
  },

  "nuevos": [
    {
      "id": "x:InscripcionService.inscribir",
      "nombre": "inscribir()",
      "nivel": "codigo",
      "tipo": "metodo",
      "padre": "k:backend/src/main/java/ar/edu/unla/eventos/service/InscripcionService.java",
      "archivo": "backend/src/main/java/ar/edu/unla/eventos/service/InscripcionService.java",
      "desde": 24, "hasta": 41,
      "resumen": "Verifica cupo, crea la inscripción y descuenta el lugar.",
      "porque": "@Transactional: si falla el insert, el cupo no queda descontado."
    }
  ],

  "relaciones": [
    { "de": "k:frontend/src/api/client.js", "a": "c:backend", "etiqueta": "HTTP REST (axios)" }
  ],
  "quitar_relaciones": [
    { "de": "k:…", "a": "k:…" }
  ],

  "flujos": [
    {
      "id": "inscripcion",
      "nombre": "Inscribirse a un evento",
      "resumen": "Desde el click en 'Inscribirme' hasta el INSERT en la base.",
      "actor": "Estudiante",
      "pasos": [
        {
          "nodo": "k:frontend/src/pages/EventoDetalle.jsx",
          "accion": "click en Inscribirme",
          "desde": 30, "hasta": 38,
          "explicacion": "El handler llama al servicio de API con el id del evento."
        },
        {
          "nodo": "k:backend/src/main/java/ar/edu/unla/eventos/controller/InscripcionController.java",
          "accion": "POST /api/eventos/{id}/inscripciones",
          "desde": 22, "hasta": 29,
          "explicacion": "Valida el DTO y delega en el service. No tiene lógica de negocio.",
          "pregunta": "¿Por qué el controller no consulta el repositorio directamente?"
        }
      ]
    }
  ]
}
```

## Reglas de contenido

| Campo | Regla |
|---|---|
| `resumen` | Qué hace, 1–2 frases. Sin "Este componente se encarga de…". |
| `porque` | La decisión y su coste o alternativa. Si no hay decisión interesante, omitilo: no repitas el resumen. |
| `pregunta` | Solo donde haya algo para razonar (como máximo 1 de cada 3 nodos). Que no se responda con sí/no. |
| `accion` (paso) | Lo que se ve en la flecha: verbo + objeto, máx. ~5 palabras, o el endpoint. |
| `explicacion` (paso) | Qué pasa en este paso y por qué, 1–3 frases. |
| `desde`/`hasta` | Las líneas clave, no la clase entera. `build.py` corta en 60 líneas. |

## IDs

Copialos exactos del árbol que imprime `extract.py`:

- `sistema`: la raíz (se configura con `proyecto`, no en `nodos`).
- `c:<dir>`: contenedor de código; `c:svc.<nombre>`: servicio de docker-compose (DB, etc.).
- `m:<contenedor>:<módulo>`: paquete Java o directorio.
- `k:<ruta/al/archivo>`: componente (una clase o un archivo).
- `nuevos`: usá el prefijo `x:` para lo que inventás vos (métodos clave, conceptos).

Si `build.py` avisa sobre un ID inexistente, el esqueleto cambió (archivo renombrado o movido): corregí el ID, no lo ignores.
