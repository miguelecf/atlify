import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { type Appointment, cancelAppointment, listAppointments } from "../api/appointments"

export function AppointmentsPage() {
  const [items, setItems] = useState<Appointment[]>([])

  useEffect(() => {
    listAppointments().then(setItems)
  }, [])

  async function onCancel(id: number) {
    if (!confirm("¿Cancelar el turno?")) return
    await cancelAppointment(id)
    setItems((prev) => prev.map((a) => (a.id === id ? { ...a, status: "cancelled" } : a)))
  }

  return (
    <section>
      <h1>Mis turnos</h1>
      <Link to="/turnos/nuevo">Reservar turno</Link>
      <ul>
        {items.map((a) => (
          <li key={a.id}>
            {a.pet_name} · {a.service_name} · {new Date(a.starts_at).toLocaleString()}
            {a.status === "scheduled" && <button onClick={() => onCancel(a.id)}>Cancelar</button>}
          </li>
        ))}
      </ul>
    </section>
  )
}
