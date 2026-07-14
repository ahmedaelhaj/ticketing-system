import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

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

export default function Dashboard() {
  const { user } = useAuth()
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/tickets').then(({ data }) => setTickets(data)).finally(() => setLoading(false))
  }, [])

  const counts = tickets.reduce((acc, t) => {
    if (t.status === 'pending_approval') {
      const key = t.pending_approval_stage === 2 ? 'pending_stage_2' : 'pending_stage_1'
      acc[key] = (acc[key] || 0) + 1
    } else {
      acc[t.status] = (acc[t.status] || 0) + 1
    }
    return acc
  }, {})

  const cards = [
    { key: 'pending_stage_1', label: 'Pending 1st approval', color: 'text-amber-700 bg-amber-50 border-amber-200' },
    { key: 'pending_stage_2', label: 'Pending 2nd approval', color: 'text-orange-700 bg-orange-50 border-orange-200' },
    { key: 'open', label: 'Open', color: 'text-blue-700 bg-blue-50 border-blue-200' },
    { key: 'in_progress', label: 'In progress', color: 'text-indigo-700 bg-indigo-50 border-indigo-200' },
    { key: 'closed', label: 'Closed', color: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
    { key: 'rejected', label: 'Rejected', color: 'text-rose-700 bg-rose-50 border-rose-200' },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-medium text-slate-900">Welcome back, {user?.full_name?.split(' ')[0]}</h1>
        <p className="text-sm text-slate-500 mt-1">Here's what's happening across your tickets.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        {cards.map(c => (
          <div key={c.key} className={`border rounded-xl p-4 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 ${c.color}`}>
            <div className="text-2xl font-medium">{counts[c.key] || 0}</div>
            <div className={`mt-1 leading-snug ${c.label.length > 16 ? 'text-xs' : 'text-sm'}`}>{c.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-900">Recent tickets</h2>
          <Link to="/tickets" className="text-sm text-brand-600 hover:text-brand-700">View all</Link>
        </div>
        {loading ? (
          <div className="p-6 text-sm text-slate-500">Loading...</div>
        ) : tickets.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">No tickets yet. Create your first one from the Tickets page.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">Title</th>
                <th className="px-5 py-3 font-medium">Requester</th>
                <th className="px-5 py-3 font-medium">Assigned to</th>
                <th className="px-5 py-3 font-medium">Priority</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Created</th>
                <th className="px-5 py-3 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {tickets.slice(0, 6).map(t => (
                <tr key={t.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors duration-150">
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
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
