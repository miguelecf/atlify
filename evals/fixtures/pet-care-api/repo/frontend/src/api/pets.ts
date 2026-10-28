import { api } from "./client"

export type Pet = { id: number; name: string; species: string }

export async function listPets() {
  const { data } = await api.get<Pet[]>("/api/pets")
  return data
}

export async function createPet(name: string, species: string) {
  const { data } = await api.post("/api/pets", { name, species })
  return data as { id: number }
}

export async function searchPets(q: string) {
  const { data } = await api.get<Pet[]>(`/api/pets/search?q=${q}`)
  return data
}
