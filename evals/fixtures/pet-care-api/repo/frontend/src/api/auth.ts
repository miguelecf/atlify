import { api } from "./client"

export async function login(email: string, password: string) {
  const form = new URLSearchParams({ username: email, password })
  const { data } = await api.post("/api/auth/login", form)
  localStorage.setItem("token", data.access_token)
}

export async function getMe() {
  const { data } = await api.get("/api/auth/me")
  return data as { id: number; email: string; role: string }
}
