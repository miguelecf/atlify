import { BrowserRouter, Route, Routes } from "react-router-dom"
import { AppointmentsPage } from "./pages/AppointmentsPage"
import { LoginPage } from "./pages/LoginPage"
import { NewAppointmentPage } from "./pages/NewAppointmentPage"
import { PetsPage } from "./pages/PetsPage"

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/turnos" element={<AppointmentsPage />} />
        <Route path="/turnos/nuevo" element={<NewAppointmentPage />} />
        <Route path="/mascotas" element={<PetsPage />} />
      </Routes>
    </BrowserRouter>
  )
}
