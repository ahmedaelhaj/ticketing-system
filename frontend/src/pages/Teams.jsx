import { useEffect, useState } from 'react'
import api from '../api/client'

export default function Teams() {
  const [teams, setTeams] = useState([])
  const [teamAdmins, setTeamAdmins] = useState([])
  const [form, setForm] = useState({ name: '', team_admin_id: '' })
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null) // team object being edited, or null
  const [busyId, setBusyId] = useState(null)

  function load() {
    api.get('/teams').then(({ data }) => setTeams(data))
    api.get('/users').then(({ data }) => setTeamAdmins(data.filter(u => u.role === 'team_admin')))
  }
  useEffect(load, [])

  async function createTeam(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/teams', { name: form.name, team_admin_id: form.team_admin_id || null })
      setForm({ name: '', team_admin_id: '' })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create team.')
    }
  }

  async function saveEdit(e) {
    e.preventDefault()
    setError('')
    setBusyId(editing.id)
    try {
      await api.patch(`/teams/${editing.id}`, {
        name: editing.name,
        team_admin_id: editing.team_admin_id || null,
      })
      setEditing(null)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update team.')
    } finally {
      setBusyId(null)
    }
  }

  async function deleteTeam(team) {
    if (!confirm(`Delete "${team.name}"? This can't be undone.`)) return
    setError('')
    setBusyId(team.id)
    try {
      await api.delete(`/teams/${team.id}`)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete team.')
    } finally {
      setBusyId(null)
    }
  }

  async function toggleActive(team) {
    setError('')
    setBusyId(team.id)
    try {
      await api.patch(`/teams/${team.id}`, { is_active: !team.is_active })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update team.')
    } finally {
      setBusyId(null)
    }
  }

  function adminLabel(id) {
    const a = teamAdmins.find(a => a.id === id)
    return a ? `${a.full_name} (${a.email})` : '— not assigned —'
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-xl font-medium text-slate-900">Teams</h1>
        <p className="text-sm text-slate-500 mt-1">
          Create teams with their admin. Only users with the <span className="font-medium">team_admin</span> role
          appear in the dropdown — create one on the Users page first if it's empty.
        </p>
      </div>

      {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-4">{error}</div>}

      <form onSubmit={createTeam} className="bg-white border border-slate-200 rounded-xl p-5 flex gap-3 mb-6">
        <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Team name" required
          className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        <select value={form.team_admin_id} onChange={e => setForm({ ...form, team_admin_id: e.target.value })}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-64">
          <option value="">— not assigned —</option>
          {teamAdmins.map(a => <option key={a.id} value={a.id}>{a.full_name} ({a.email})</option>)}
        </select>
        <button className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg whitespace-nowrap">Add team</button>
      </form>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wide">
              <th className="px-5 py-3 font-medium">Team</th>
              <th className="px-5 py-3 font-medium">Team admin</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {teams.map(t => (
              <tr key={t.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors duration-150">
                <td className="px-5 py-3 font-medium text-slate-900">{t.name}</td>
                <td className="px-5 py-3 text-slate-500">{adminLabel(t.team_admin_id)}</td>
                <td className="px-5 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${t.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {t.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-5 py-3 text-right">
                  <button onClick={() => toggleActive(t)} disabled={busyId === t.id}
                    className="text-slate-600 hover:text-slate-800 text-sm font-medium mr-4 disabled:opacity-50">
                    {t.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button onClick={() => setEditing({ ...t })} className="text-brand-600 hover:text-brand-700 text-sm font-medium mr-4">Edit</button>
                  <button onClick={() => deleteTeam(t)} disabled={busyId === t.id}
                    className="text-rose-600 hover:text-rose-700 text-sm font-medium disabled:opacity-50">Delete</button>
                </td>
              </tr>
            ))}
            {teams.length === 0 && (
              <tr><td colSpan={4} className="px-5 py-8 text-center text-sm text-slate-500">No teams yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4 animate-backdrop">
          <div className="bg-white rounded-xl w-full max-w-md p-6 animate-modal">
            <h2 className="text-lg font-medium text-slate-900 mb-4">Edit team</h2>
            <form onSubmit={saveEdit} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-700 mb-1">Team name</label>
                <input required value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm text-slate-700 mb-1">Team admin</label>
                <select value={editing.team_admin_id || ''} onChange={e => setEditing({ ...editing, team_admin_id: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">— not assigned —</option>
                  {teamAdmins.map(a => <option key={a.id} value={a.id}>{a.full_name} ({a.email})</option>)}
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
