# Ejemplos

El atlas completo de referencia es `evals/fixtures/pet-care-api/atlas.json`, sobre el repo de `evals/fixtures/pet-care-api/repo/`. Acá van fragmentos comentados para calibrar.

## Un paso

Flojo: repite lo que dice el código.

```json
{ "archivo": "backend/app/routers/appointments.py", "simbolo": "create_appointment",
  "accion": "Crea el turno", "explicacion": "Este endpoint crea un turno llamando al service." }
```

Bien: explica el mecanismo y la decisión.

```json
{ "archivo": "backend/app/routers/appointments.py", "simbolo": "create_appointment",
  "accion": "Valida y delega",
  "explicacion": "FastAPI valida el body contra AppointmentCreate (si falta un campo, devuelve 422 sin ejecutar nada). El router solo traduce SlotTaken a 409.",
  "pregunta": "¿Por qué conviene que el router no sepa cómo se decide si un horario está ocupado?" }
```

## Un hallazgo

Flojo: sin escenario, sin ubicación precisa y sin arreglo.

```json
{ "id": "auth", "severidad": "alta", "origen": "agente", "titulo": "Problema de seguridad en DELETE",
  "explicacion": "Falta autenticación.", "sugerencia": "Agregar auth.", "archivo": "backend/app/routers/appointments.py" }
```

Bien: título con la consecuencia, escenario concreto y arreglo mínimo en su lugar.

```json
{
  "id": "h-delete-sin-auth", "severidad": "alta", "origen": "agente", "categoria": "Seguridad",
  "titulo": "Cualquiera puede cancelar cualquier turno",
  "explicacion": "DELETE /api/appointments/{id} no exige sesión ni comprueba que el turno sea del usuario. Alguien sin cuenta puede cancelar todos los turnos probando ids del 1 en adelante.",
  "sugerencia": "Agregar user: User = Depends(get_current_user) en el router y, en el service, verificar que a.pet.owner_id == user.id antes de cancelar.",
  "archivo": "backend/app/routers/appointments.py", "simbolo": "cancel_appointment",
  "endpoint": "DELETE /api/appointments/{appointment_id}"
}
```

## Hallazgos que solo aparecen leyendo con criterio

En el fixture, el script encuentra 3 cosas (la búsqueda rota y 2 endpoints sin uso). Las demás requieren seguir el recorrido:

| Hallazgo | Cómo se encuentra |
|---|---|
| N+1 al listar turnos | Contar consultas: un bucle de mascotas, una consulta de turnos por mascota y `a.pet`/`a.service` cargados uno por uno en `_to_out`. |
| Reserva duplicada por carrera | `exists_at` y después `add`, sin UNIQUE en `appointments`. Mirar el modelo para confirmar que falta la restricción. |
| Error 500 con mascota ajena | `book` lanza `PermissionError` y el router solo atrapa `SlotTaken`. |
| Hash de la contraseña expuesto | `get_pet` devuelve `pet.owner` sin `response_model`, y `User` tiene `password_hash`. |
| Catálogo copiado en el frontend | `GET /api/services` existe y nadie lo usa, y `NewAppointmentPage` tiene `SERVICES` fijo. Son dos hechos que solo juntos explican el problema. |

## Una sospecha que no es hallazgo

Si `duration_min` existe pero nadie lo usa para evitar turnos superpuestos, no lo afirmes como bug sin saber la regla del negocio. Va como pregunta:

```json
"pregunta": "duration_min no se usa al reservar: ¿dos turnos de 60 minutos pueden empezar con 30 minutos de diferencia?"
```

## Reporte final

```text
Atlas: .atlas/atlas.html
Cubre 9 de 9 endpoints y 4 tablas.
Hallazgos: 4 altos, 5 medios, 2 bajos. Los más graves:
- Cualquiera puede cancelar cualquier turno (appointments.py: cancel_appointment)
- La búsqueda de mascotas llama a una ruta que no existe (pets.ts: searchPets)
- El detalle de mascota devuelve el hash de la contraseña del dueño (pets.py: get_pet)
Sin explicar: App.tsx (solo rutas). Sugerencia: agregá .atlas/ al .gitignore o versioná solo atlas.json.
```
