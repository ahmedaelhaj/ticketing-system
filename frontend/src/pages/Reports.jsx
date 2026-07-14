import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

const STATUS_PILL = {
  pending_approval: 'bg-amber-100 text-amber-800',
  open: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-indigo-100 text-indigo-800',
  closed: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-rose-100 text-rose-800',
}
const STATUS_LABEL = {
  pending_approval: 'Pending approval', open: 'Open', in_progress: 'In progress',
  closed: 'Closed', rejected: 'Rejected',
}
const STATUS_ORDER = ['pending_approval', 'open', 'in_progress', 'closed', 'rejected']

export default function Reports() {
  const { user } = useAuth()
  const [scope, setScope] = useState(user.role === 'super_admin' ? 'global' : (user.role === 'team_admin' ? 'team' : 'mine'))
  const [teamId, setTeamId] = useState(user.team_id || '')
  const [statusFilter, setStatusFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [busyFmt, setBusyFmt] = useState(null)
  const [justDownloaded, setJustDownloaded] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [summaryError, setSummaryError] = useState('')

  const baseParams = {
    scope,
    ...(scope !== 'mine' && teamId ? { team_id: teamId } : {}),
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
  }

  useEffect(() => {
    setSummaryLoading(true)
    setSummaryError('')
    const t = setTimeout(() => {
      api.get('/reports/summary', { params: baseParams })
        .then(({ data }) => setSummary(data))
        .catch(err => setSummaryError(err.response?.data?.detail || 'Could not load preview.'))
        .finally(() => setSummaryLoading(false))
    }, 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, teamId, statusFilter, dateFrom, dateTo])

  async function download(fmt) {
    setBusyFmt(fmt)
    setJustDownloaded(null)
    try {
      let url = '/reports/me'
      if (scope === 'team') url = `/reports/team/${teamId || user.team_id}`
      if (scope === 'global') url = '/reports/global'

      const { data, headers } = await api.get(url, { params: { ...baseParams, format: fmt }, responseType: 'blob' })
      const blob = new Blob([data], { type: headers['content-type'] })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `ticket_report.${fmt}`
      link.click()
      setJustDownloaded(fmt)
      setTimeout(() => setJustDownloaded(null), 2500)
    } finally {
      setBusyFmt(null)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="mb-6">
        <h1 className="text-xl font-medium text-slate-900">Reports</h1>
        <p className="text-sm text-slate-500 mt-1">Export ticket activity as a PDF or Excel file.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        {user.role !== 'normal_user' && (
          <div>
            <label className="block text-sm text-slate-700 mb-1">Scope</label>
            <div className="flex gap-2">
              <button type="button" onClick={() => setScope('mine')}
                className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors duration-150 ${scope === 'mine' ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200'}`}>
                My tickets
              </button>
              <button type="button" onClick={() => setScope('team')}
                className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors duration-150 ${scope === 'team' ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200'}`}>
                {user.role === 'super_admin' ? 'A team' : 'My team'}
              </button>
              {user.role === 'super_admin' && (
                <button type="button" onClick={() => setScope('global')}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors duration-150 ${scope === 'global' ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-600 border-slate-200'}`}>
                  Everything
                </button>
              )}
            </div>
          </div>
        )}

        {user.role === 'normal_user' && (
          <p className="text-xs text-slate-500">This exports every ticket you created or that's currently assigned to you.</p>
        )}

        {scope === 'team' && (
          <div>
            <label className="block text-sm text-slate-700 mb-1">
              {user.role === 'super_admin' ? 'Team ID' : 'Your team'}
            </label>
            {user.role === 'super_admin' ? (
              <input value={teamId} onChange={e => setTeamId(e.target.value)} placeholder="Team ID"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            ) : (
              <p className="text-xs text-slate-500">
                Includes every ticket your team currently owns, plus every ticket your team originally requested —
                even ones now handled or closed by another team. Full audit trail.
              </p>
            )}
          </div>
        )}

        {scope === 'global' && (
          <div>
            <label className="block text-sm text-slate-700 mb-1">Team ID (leave blank for all teams)</label>
            <input value={teamId} onChange={e => setTeamId(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        )}

        <div>
          <label className="block text-sm text-slate-700 mb-1">Status filter</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="">All statuses</option>
            {STATUS_ORDER.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-slate-700 mb-1">Created from</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">Created to</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        </div>

        {/* Live preview of what this will export */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          {summaryError ? (
            <p className="text-xs text-rose-600">{summaryError}</p>
          ) : summaryLoading ? (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <i className="ti ti-loader-2 animate-spin"></i> Updating preview...
            </div>
          ) : summary ? (
            <>
              <div className="text-sm text-slate-800 mb-1.5">
                <span className="font-semibold">{summary.total}</span> ticket{summary.total === 1 ? '' : 's'} will be included
              </div>
              {summary.total > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {STATUS_ORDER.filter(s => summary.by_status[s]).map(s => (
                    <span key={s} className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_PILL[s]}`}>
                      {STATUS_LABEL[s]} · {summary.by_status[s]}
                    </span>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>

        <div className="flex gap-2 pt-2">
          <button disabled={busyFmt !== null || summary?.total === 0} onClick={() => download('pdf')}
            className="flex-1 px-4 py-2 text-sm bg-slate-900 hover:bg-slate-800 transition-colors duration-150 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2">
            {busyFmt === 'pdf' ? (
              <><i className="ti ti-loader-2 animate-spin"></i> Generating...</>
            ) : justDownloaded === 'pdf' ? (
              <><i className="ti ti-check"></i> Downloaded</>
            ) : (
              <><i className="ti ti-file-type-pdf"></i> Download PDF</>
            )}
          </button>
          <button disabled={busyFmt !== null || summary?.total === 0} onClick={() => download('xlsx')}
            className="flex-1 px-4 py-2 text-sm bg-white border border-slate-300 hover:bg-slate-50 transition-colors duration-150 text-slate-700 rounded-lg disabled:opacity-50 flex items-center justify-center gap-2">
            {busyFmt === 'xlsx' ? (
              <><i className="ti ti-loader-2 animate-spin"></i> Generating...</>
            ) : justDownloaded === 'xlsx' ? (
              <><i className="ti ti-check text-emerald-600"></i> Downloaded</>
            ) : (
              <><i className="ti ti-file-spreadsheet"></i> Download Excel</>
            )}
          </button>
        </div>
        {summary?.total === 0 && (
          <p className="text-xs text-slate-400 text-center">No tickets match these filters — nothing to export yet.</p>
        )}
      </div>

      {(user.role === 'team_admin' || user.role === 'super_admin') && <PerformanceLeaderboard user={user} />}
    </div>
  )
}

function PerformanceLeaderboard({ user }) {
  const [data, setData] = useState([])
  const [teamId, setTeamId] = useState('')
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState('closed_count')

  function load() {
    setLoading(true)
    const params = teamId ? { team_id: teamId } : {}
    api.get('/reports/performance', { params }).then(({ data }) => setData(data)).finally(() => setLoading(false))
  }

  useEffect(load, [teamId])

  const sorted = data.slice().sort((a, b) => {
    if (sortKey === 'avg_close_hours') return (a.avg_close_hours ?? Infinity) - (b.avg_close_hours ?? Infinity)
    if (sortKey === 'full_name') return a.full_name.localeCompare(b.full_name)
    return b.closed_count - a.closed_count
  })

  const maxCount = Math.max(1, ...sorted.map(d => d.closed_count))

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 mt-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-sm font-medium text-slate-900">Who's closing tickets</h2>
        <i className="ti ti-trophy text-amber-500"></i>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        {user.role === 'super_admin'
          ? 'Ranked by tickets actually closed — credit goes to whoever performed the close, not just whoever it was assigned to.'
          : 'Ranked by tickets actually closed within your team.'}
      </p>

      {user.role === 'super_admin' && (
        <input
          value={teamId} onChange={e => setTeamId(e.target.value)} placeholder="Filter by team ID (optional)"
          className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      )}

      {data.length > 0 && (
        <div className="flex items-center gap-1 mb-3 text-xs text-slate-500">
          Sort by:
          {[
            { key: 'closed_count', label: 'Most closed' },
            { key: 'avg_close_hours', label: 'Fastest avg' },
            { key: 'full_name', label: 'Name' },
          ].map(o => (
            <button key={o.key} onClick={() => setSortKey(o.key)}
              className={`px-2 py-0.5 rounded-full border transition-colors duration-150 ${
                sortKey === o.key ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300'
              }`}>
              {o.label}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-400">Loading...</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-slate-400">No closed tickets yet.</p>
      ) : (
        <div className="space-y-3">
          {sorted.map((d, i) => (
            <div key={d.user_id} className="animate-row-enter" style={{ animationDelay: `${i * 40}ms` }}>
              <div className="flex items-center justify-between text-sm mb-1">
                <div className="flex items-center gap-2">
                  <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold ${
                    i === 0 ? 'bg-amber-100 text-amber-700' : i === 1 ? 'bg-slate-200 text-slate-600' : i === 2 ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500'
                  }`}>{i + 1}</span>
                  <span className="font-medium text-slate-800">{d.full_name}</span>
                  {d.team_name && <span className="text-xs text-slate-400">· {d.team_name}</span>}
                </div>
                <div className="text-slate-500 text-xs">
                  {d.closed_count} closed{d.avg_close_hours != null && ` · avg ${d.avg_close_hours}h`}
                </div>
              </div>
              <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-full transition-all duration-500"
                  style={{ width: `${(d.closed_count / maxCount) * 100}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
