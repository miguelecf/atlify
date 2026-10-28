import { useEffect, useState } from "react"
import { type Pet, createPet, listPets, searchPets } from "../api/pets"

export function PetsPage() {
  const [pets, setPets] = useState<Pet[]>([])
  const [q, setQ] = useState("")

  useEffect(() => {
    listPets().then(setPets)
  }, [])

  async function onSearch(value: string) {
    setQ(value)
    setPets(value ? await searchPets(value) : await listPets())
  }

  async function onAdd() {
    const name = prompt("Nombre de la mascota")
    if (!name) return
    await createPet(name, "perro")
    setPets(await listPets())
  }

  return (
    <section>
      <h1>Mis mascotas</h1>
      <input value={q} onChange={(e) => onSearch(e.target.value)} placeholder="Buscar…" />
      <button onClick={onAdd}>Agregar</button>
      <ul>{pets.map((p) => <li key={p.id}>{p.name} ({p.species})</li>)}</ul>
    </section>
  )
}
