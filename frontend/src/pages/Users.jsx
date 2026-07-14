import { useEffect, useState } from 'react'
import api from '../api/client'

export default function Users() {
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'normal_user', team_id: '' })
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [editing, setEditing] = useState(null)

  function load() {
    api.get('/users').then(({ data }) => setUsers(data))
    api.get('/teams').then(({ data }) => setTeams(data))
  }
  useEffect(load, [])

  async function createUser(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/users', { ...form, team_id: form.team_id || null })
      setForm({ email: '', password: '', full_name: '', role: 'normal_user', team_id: '' })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create user.')
    }
  }

  async function toggleActive(u) {
    setBusyId(u.id)
    setError('')
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update user.')
    } finally {
      setBusyId(null)
    }
  }

  async function saveEdit(e) {
    e.preventDefault()
    setError('')
    setBusyId(editing.id)
    try {
      await api.patch(`/users/${editing.id}`, {
        full_name: editing.full_name,
        email: editing.email,
        role: editing.role,
        team_id: editing.team_id || null,
      })
      setEditing(null)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update user.')
    } finally {
      setBusyId(null)
    }
  }

  async function deleteUser(user) {
    if (!confirm(`Delete ${user.full_name} (${user.email})? This can't be undone.`)) return
    setBusyId(user.id)
    setError('')
    try {
      await api.delete(`/users/${user.id}`)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete user.')
    } finally {
      setBusyId(null)
    }
  }

  function teamName(id) {
    const t = teams.find(t => t.id === id)
    return t ? t.name : '—'
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-medium text-slate-900">Users</h1>
        <p className="text-sm text-slate-500 mt-1">Create accounts, edit their details, or remove them.</p>
      </div>

      {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-4">{error}</div>}

      <form onSubmit={createUser} className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-3 mb-6">
        <input placeholder="Full name" required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        <input placeholder="Email" type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        <input placeholder="Temporary password" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm" />
        <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
          <option value="normal_user">Normal user</option>
          <option value="team_admin">Team admin</option>
          <option value="super_admin">Super admin</option>
        </select>
        <select value={form.team_id} onChange={e => setForm({ ...form, team_id: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm col-span-2">
          <option value="">No team</option>
          {teams.filter(t => t.is_active).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button className="col-span-2 px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg">Create user</button>
      </form>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wide">
              <th className="px-5 py-3 font-medium">Name</th>
              <th className="px-5 py-3 font-medium">Email</th>
              <th className="px-5 py-3 font-medium">Role</th>
              <th className="px-5 py-3 font-medium">Team</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors duration-150">
                <td className="px-5 py-3 font-medium text-slate-900">{u.full_name}</td>
                <td className="px-5 py-3 text-slate-500">{u.email}</td>
                <td className="px-5 py-3 text-slate-500 capitalize">{u.role.replace('_', ' ')}</td>
                <td className="px-5 py-3 text-slate-500">{teamName(u.team_id)}</td>
                <td className="px-5 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-5 py-3 text-right">
                  <button onClick={() => setEditing({ ...u })} className="text-brand-600 hover:text-brand-700 text-sm font-medium mr-4">Edit</button>
                  <button onClick={() => toggleActive(u)} disabled={busyId === u.id}
                    className="text-slate-600 hover:text-slate-800 text-sm font-medium mr-4 disabled:opacity-50">
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button onClick={() => deleteUser(u)} disabled={busyId === u.id}
                    className="text-rose-600 hover:text-rose-700 text-sm font-medium disabled:opacity-50">Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4 animate-backdrop">
          <div className="bg-white rounded-xl w-full max-w-md p-6 animate-modal">
            <h2 className="text-lg font-medium text-slate-900 mb-4">Edit user</h2>
            <form onSubmit={saveEdit} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-700 mb-1">Full name</label>
                <input required value={editing.full_name} onChange={e => setEditing({ ...editing, full_name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm text-slate-700 mb-1">Email</label>
                <input required type="email" value={editing.email} onChange={e => setEditing({ ...editing, email: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm text-slate-700 mb-1">Role</label>
                <select value={editing.role} onChange={e => setEditing({ ...editing, role: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="normal_user">Normal user</option>
                  <option value="team_admin">Team admin</option>
                  <option value="super_admin">Super admin</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-700 mb-1">Team</label>
                <select value={editing.team_id || ''} onChange={e => setEditing({ ...editing, team_id: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">No team</option>
                  {teams.filter(t => t.is_active || t.id === editing.team_id).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <button type="button" onClick={() => setEditing(null)} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
                <button disabled={busyId === editing.id} className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg disabled:opacity-60">
                  {busyId === editing.id ? 'Saving...' : 'Save changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
