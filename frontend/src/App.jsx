import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Tickets from './pages/Tickets'
import TicketDetail from './pages/TicketDetail'
import Approvals from './pages/Approvals'
import Reports from './pages/Reports'
import Teams from './pages/Teams'
import Users from './pages/Users'
import Account from './pages/Account'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/tickets" element={<Tickets />} />
        <Route path="/tickets/:id" element={<TicketDetail />} />
        <Route path="/approvals" element={<ProtectedRoute roles={['team_admin', 'super_admin']}><Approvals /></ProtectedRoute>} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/teams" element={<ProtectedRoute roles={['super_admin']}><Teams /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute roles={['super_admin']}><Users /></ProtectedRoute>} />
        <Route path="/account" element={<Account />} />
      </Route>
    </Routes>
  )
}
