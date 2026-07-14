import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { useAuth } from '../context/AuthContext'

function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(createdIso, closedIso) {
  if (!createdIso) return '—'
  const start = new Date(createdIso)
  const end = closedIso ? new Date(closedIso) : new Date()
  const totalMinutes = Math.max(0, Math.floor((end - start) / (1000 * 60)))

  let label
  if (totalMinutes < 60) {
    label = `${totalMinutes}m`
  } else if (totalMinutes < 60 * 24) {
    const hours = Math.floor(totalMinutes / 60)
    const mins = totalMinutes % 60
    label = mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  } else {
    const days = Math.floor(totalMinutes / (60 * 24))
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60)
    label = hours > 0 ? `${days}d ${hours}h` : `${days}d`
  }
  return closedIso ? label : `${label} (ongoing)`
}

function durationMinutes(createdIso, closedIso) {
  if (!createdIso) return 0
  const start = new Date(createdIso)
  const end = closedIso ? new Date(closedIso) : new Date()
  return Math.max(0, Math.floor((end - start) / (1000 * 60)))
}

const PRIORITY_RANK = { low: 0, medium: 1, high: 2, urgent: 3 }

export default function Tickets() {
  const [tickets, setTickets] = useState([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [sort, setSort] = useState({ key: 'created_at', dir: 'desc' })
  const [colFilters, setColFilters] = useState({ title: '', requester: '', assignee: '', priority: '' })

  function load() {
    setLoading(true)
    const params = status ? { status } : {}
    api.get('/tickets', { params }).then(({ data }) => setTickets(data)).finally(() => setLoading(false))
  }

  useEffect(load, [status])

  function toggleSort(key) {
    setSort(s => s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' })
  }

  function sortIcon(key) {
    if (sort.key !== key) return <i className="ti ti-arrows-sort text-slate-300"></i>
    return <i className={`ti ${sort.dir === 'asc' ? 'ti-sort-ascending' : 'ti-sort-descending'} text-slate-600`}></i>
  }

  const visibleTickets = tickets
    .filter(t => t.title.toLowerCase().includes(colFilters.title.toLowerCase()))
    .filter(t => (t.created_by_name || '').toLowerCase().includes(colFilters.requester.toLowerCase()))
    .filter(t => (t.assigned_to_name || '').toLowerCase().includes(colFilters.assignee.toLowerCase()))
    .filter(t => !colFilters.priority || t.priority === colFilters.priority)
    .slice()
    .sort((a, b) => {
      let av, bv
      switch (sort.key) {
        case 'title': av = a.title.toLowerCase(); bv = b.title.toLowerCase(); break
        case 'requester': av = (a.created_by_name || '').toLowerCase(); bv = (b.created_by_name || '').toLowerCase(); break
        case 'assignee': av = (a.assigned_to_name || '').toLowerCase(); bv = (b.assigned_to_name || '').toLowerCase(); break
        case 'priority': av = PRIORITY_RANK[a.priority] ?? -1; bv = PRIORITY_RANK[b.priority] ?? -1; break
        case 'status': av = a.status; bv = b.status; break
        case 'duration': av = durationMinutes(a.created_at, a.closed_at); bv = durationMinutes(b.created_at, b.closed_at); break
        default: av = new Date(a.created_at).getTime(); bv = new Date(b.created_at).getTime()
      }
      if (av < bv) return sort.dir === 'asc' ? -1 : 1
      if (av > bv) return sort.dir === 'asc' ? 1 : -1
      return 0
    })

  const hasActiveColFilters = Object.values(colFilters).some(v => v)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-medium text-slate-900">Tickets</h1>
          <p className="text-sm text-slate-500 mt-1">Track and manage your tasks.</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white text-sm font-medium px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <i className="ti ti-plus"></i> New ticket
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {['', 'pending_approval', 'open', 'in_progress', 'closed', 'rejected'].map(s => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
              status === s ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            {s === '' ? 'All' : s.replace('_', ' ')}
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-6 text-sm text-slate-500">Loading...</div>
        ) : tickets.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            <i className="ti ti-ticket-off text-3xl text-slate-300 block mb-2"></i>
            No tickets match this filter.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('title')}>
                  <span className="flex items-center gap-1">Title {sortIcon('title')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('requester')}>
                  <span className="flex items-center gap-1">Requester {sortIcon('requester')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('assignee')}>
                  <span className="flex items-center gap-1">Assigned to {sortIcon('assignee')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('priority')}>
                  <span className="flex items-center gap-1">Priority {sortIcon('priority')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('status')}>
                  <span className="flex items-center gap-1">Status {sortIcon('status')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('created_at')}>
                  <span className="flex items-center gap-1">Created {sortIcon('created_at')}</span>
                </th>
                <th className="px-5 py-3 font-medium cursor-pointer select-none hover:text-slate-700" onClick={() => toggleSort('duration')}>
                  <span className="flex items-center gap-1">Duration {sortIcon('duration')}</span>
                </th>
              </tr>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-2">
                  <input value={colFilters.title} onChange={e => setColFilters({ ...colFilters, title: e.target.value })}
                    placeholder="Filter title..." className="w-full px-2 py-1 border border-slate-200 rounded text-xs font-normal focus:outline-none focus:ring-1 focus:ring-brand-500" />
                </th>
                <th className="px-5 py-2">
                  <input value={colFilters.requester} onChange={e => setColFilters({ ...colFilters, requester: e.target.value })}
                    placeholder="Filter requester..." className="w-full px-2 py-1 border border-slate-200 rounded text-xs font-normal focus:outline-none focus:ring-1 focus:ring-brand-500" />
                </th>
                <th className="px-5 py-2">
                  <input value={colFilters.assignee} onChange={e => setColFilters({ ...colFilters, assignee: e.target.value })}
                    placeholder="Filter assignee..." className="w-full px-2 py-1 border border-slate-200 rounded text-xs font-normal focus:outline-none focus:ring-1 focus:ring-brand-500" />
                </th>
                <th className="px-5 py-2">
                  <select value={colFilters.priority} onChange={e => setColFilters({ ...colFilters, priority: e.target.value })}
                    className="w-full px-2 py-1 border border-slate-200 rounded text-xs font-normal focus:outline-none focus:ring-1 focus:ring-brand-500">
                    <option value="">All</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </th>
                <th className="px-5 py-2" colSpan={3}>
                  {hasActiveColFilters && (
                    <button onClick={() => setColFilters({ title: '', requester: '', assignee: '', priority: '' })}
                      className="text-xs text-brand-600 hover:text-brand-700 font-normal flex items-center gap-1">
                      <i className="ti ti-x"></i> Clear filters
                    </button>
                  )}
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleTickets.map((t, i) => (
                <tr key={t.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors duration-150 animate-row-enter" style={{ animationDelay: `${Math.min(i, 12) * 25}ms` }}>
                  <td className="px-5 py-3">
                    <Link to={`/tickets/${t.id}`} className="text-slate-900 font-medium hover:text-brand-600">{t.title}</Link>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {t.origin_team_name || t.team_name || 'no team'}
                      {(t.requested_team_name || (t.team_name && t.origin_team_name && t.team_name !== t.origin_team_name)) && (
                        <span> → {t.requested_team_name || t.team_name}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-slate-500">
                    <div>{t.created_by_name || '—'}</div>
                    <div className="text-xs text-slate-400">{t.origin_team_name || t.team_name || '—'}</div>
                  </td>
                  <td className="px-5 py-3 text-slate-500">
                    {t.assigned_to_name ? (
                      <>
                        <div>{t.assigned_to_name}</div>
                        <div className="text-xs text-slate-400">{t.team_name || '—'}</div>
                      </>
                    ) : '— unassigned —'}
                  </td>
                  <td className="px-5 py-3 text-slate-500 capitalize">{t.priority}</td>
                  <td className="px-5 py-3"><StatusBadge status={t.status} /></td>
                  <td className="px-5 py-3 text-slate-400 whitespace-nowrap">{formatDateTime(t.created_at)}</td>
                  <td className="px-5 py-3 text-slate-400 whitespace-nowrap">{formatDuration(t.created_at, t.closed_at)}</td>
                </tr>
              ))}
              {visibleTickets.length === 0 && (
                <tr><td colSpan={7} className="px-5 py-8 text-center text-sm text-slate-500">No tickets match these filters.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && <CreateTicketModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load() }} />}
    </div>
  )
}

function CreateTicketModal({ onClose, onCreated }) {
  const { user } = useAuth()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('medium')
  const [targetTeamId, setTargetTeamId] = useState('')
  const [requestedAssignedTo, setRequestedAssignedTo] = useState('')
  const [teams, setTeams] = useState([])
  const [targetMembers, setTargetMembers] = useState([])
  const [files, setFiles] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/teams').then(({ data }) => {
      setTeams(data)
      if (user?.team_id) setTargetTeamId(user.team_id)
    })
  }, [user])

  const ownTeam = teams.find(t => t.id === user?.team_id)
  const isCrossTeam = user?.team_id && targetTeamId && targetTeamId !== user.team_id

  useEffect(() => {
    setRequestedAssignedTo('')
    if (!isCrossTeam || !targetTeamId) { setTargetMembers([]); return }
    api.get(`/users/team/${targetTeamId}`).then(({ data }) => setTargetMembers(data)).catch(() => setTargetMembers([]))
  }, [targetTeamId, isCrossTeam])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data: ticket } = await api.post('/tickets', {
        title, description, priority,
        target_team_id: targetTeamId || null,
        requested_assigned_to: requestedAssignedTo || null,
      })

      for (const file of files) {
        const form = new FormData()
        form.append('file', file)
        await api.post(`/tickets/${ticket.id}/attachments`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      }

      onCreated()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create ticket.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4 overflow-y-auto animate-backdrop">
      <div className="bg-white rounded-xl w-full max-w-md p-6 my-8 animate-modal">
        <h2 className="text-lg font-medium text-slate-900 mb-4">Create ticket</h2>
        <form onSubmit={submit} className="space-y-4">
          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{error}</div>}
          <div>
            <label className="block text-sm text-slate-700 mb-1">Title</label>
            <input required value={title} onChange={e => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">Description</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">Priority</label>
            <select value={priority} onChange={e => setPriority(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>

          {user?.role === 'super_admin' ? (
            <div>
              <label className="block text-sm text-slate-700 mb-1">Team</label>
              <select value={targetTeamId} onChange={e => setTargetTeamId(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">No team</option>
                {teams.filter(t => t.is_active).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-sm text-slate-700 mb-1">Send this ticket to</label>
              <select value={targetTeamId} onChange={e => setTargetTeamId(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                {ownTeam && <option value={ownTeam.id}>{ownTeam.name} (my team)</option>}
                {teams.filter(t => t.id !== user?.team_id && t.is_active).map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              {isCrossTeam ? (
                <p className="text-xs text-amber-600 mt-1">
                  This goes to your team admin first for authorization, then to {teams.find(t => t.id === targetTeamId)?.name}'s
                  admin for final approval — two approvals required.
                </p>
              ) : (
                <p className="text-xs text-slate-500 mt-1">Your team admin will review and approve this ticket.</p>
              )}
            </div>
          )}

          {isCrossTeam && targetMembers.length > 0 && (
            <div>
              <label className="block text-sm text-slate-700 mb-1">Specifically for (optional)</label>
              <select value={requestedAssignedTo} onChange={e => setRequestedAssignedTo(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">No preference — let the team admin decide</option>
                {targetMembers.map(m => <option key={m.id} value={m.id}>{m.full_name} ({m.email})</option>)}
              </select>
              <p className="text-xs text-slate-500 mt-1">A suggestion for who should handle this — the approving admin can still change it.</p>
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-700 mb-1">Attachments (optional)</label>
            <input type="file" multiple onChange={e => setFiles(Array.from(e.target.files))}
              className="w-full text-sm text-slate-600 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700 file:text-sm hover:file:bg-slate-200" />
            {files.length > 0 && (
              <ul className="mt-1 text-xs text-slate-500 list-disc list-inside">
                {files.map((f, i) => <li key={i}>{f.name}</li>)}
              </ul>
            )}
            <p className="text-xs text-slate-500 mt-1">Images, PDFs, Office docs, or text/CSV — visible on this ticket at every step.</p>
          </div>

          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
            <button disabled={busy} className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg disabled:opacity-60">
              {busy ? 'Creating...' : 'Create ticket'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
