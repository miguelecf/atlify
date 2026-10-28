import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { createAppointment } from "../api/appointments"
import { type Pet, listPets } from "../api/pets"

const SERVICES = [
  { id: 1, name: "Baño" },
  { id: 2, name: "Corte" },
  { id: 3, name: "Consulta" },
]

export function NewAppointmentPage() {
  const [pets, setPets] = useState<Pet[]>([])
  const [petId, setPetId] = useState(0)
  const [serviceId, setServiceId] = useState(1)
  const [startsAt, setStartsAt] = useState("")
  const [error, setError] = useState("")
  const navigate = useNavigate()

  useEffect(() => {
    listPets().then(setPets)
  }, [])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await createAppointment(petId, serviceId, startsAt)
      navigate("/turnos")
    } catch {
      setError("No se pudo reservar. Probá otro horario.")
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <select value={petId} onChange={(e) => setPetId(Number(e.target.value))}>
        {pets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select value={serviceId} onChange={(e) => setServiceId(Number(e.target.value))}>
        {SERVICES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
      {error && <p role="alert">{error}</p>}
      <button>Reservar</button>
    </form>
  )
}
