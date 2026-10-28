import { api } from "./client"

export type Appointment = { id: number; pet_name: string; service_name: string; starts_at: string; status: string }

export async function listAppointments() {
  const { data } = await api.get<Appointment[]>("/api/appointments")
  return data
}

export async function createAppointment(petId: number, serviceId: number, startsAt: string) {
  const { data } = await api.post<Appointment>("/api/appointments", {
    pet_id: petId,
    service_id: serviceId,
    starts_at: startsAt,
  })
  return data
}

export async function cancelAppointment(id: number) {
  await api.delete(`/api/appointments/${id}`)
}
