import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Approvals() {
  const { user } = useAuth()
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [comment, setComment] = useState({})
  const [assignee, setAssignee] = useState({})
  const [teamMembers, setTeamMembers] = useState({}) // teamId -> [users]
  const [error, setError] = useState({})

  function load() {
    setLoading(true)
    api.get('/approvals/pending').then(({ data }) => {
      setApprovals(data)
      // preload team members for any approval that's a final stage (needs an assignee pick)
      data.filter(a => a.is_final_stage && a.current_team_id).forEach(a => {
        if (!teamMembers[a.current_team_id]) {
          api.get(`/users/team/${a.current_team_id}`).then(({ data: members }) => {
            setTeamMembers(prev => ({ ...prev, [a.current_team_id]: members }))
          })
        }
      })
    }).finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function decide(approvalId, decision) {
    setError({ ...error, [approvalId]: '' })
    try {
      await api.post(`/approvals/${approvalId}/decide`, {
        decision,
        comment: comment[approvalId] || '',
        assigned_to: assignee[approvalId] || null,
      })
      load()
    } catch (err) {
      setError({ ...error, [approvalId]: err.response?.data?.detail || 'Could not record decision.' })
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-medium text-slate-900">Approvals</h1>
        <p className="text-sm text-slate-500 mt-1">
          {user?.role === 'super_admin'
            ? 'All tickets awaiting approval, across every team. As super admin you can decide any of these.'
            : "Tickets waiting on your decision."}
        </p>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6 text-xs text-slate-600 space-y-1.5">
        <div className="font-medium text-slate-700 mb-1">How approval works</div>
        <div><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-2"></span>
          <span className="font-medium">Same-team tickets</span> need one approval from your team — approving opens it immediately.</div>
        <div><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-2"></span>
          <span className="font-medium">Cross-team tickets</span> need two approvals: first the requester's own team admin (stage 1, authorizing the request), then the target team's admin (stage 2, final approval).</div>
        <div><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-2"></span>
          <span className="font-medium">Final approval</span> opens the ticket and lets you assign it to anyone on your team.</div>
        <div><span className="inline-block w-2 h-2 rounded-full bg-rose-500 mr-2"></span>
          <span className="font-medium">Rejecting</span> at any stage sends it back to the requester, who can edit and resubmit — always restarting at stage 1.</div>
      </div>

      {loading ? (
        <div className="text-sm text-slate-500">Loading...</div>
      ) : approvals.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-10 text-center text-sm text-slate-500">
          <i className="ti ti-checklist text-3xl text-slate-300 block mb-2"></i>
          Nothing needs approval right now.
        </div>
      ) : (
        <div className="space-y-3">
          {approvals.map(a => (
            <div key={a.id} className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <Link to={`/tickets/${a.ticket_id}`} className="text-sm font-medium text-slate-900 hover:text-brand-600">
                    {a.ticket_title || `Ticket #${a.ticket_id.slice(0, 8)}`}
                  </Link>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Requested by {a.requester_name || 'unknown'} · {a.team_name || 'no team'}
                    {a.requested_team_name && !a.is_final_stage && (
                      <span className="text-amber-600"> → routing to {a.requested_team_name}</span>
                    )}
                    {' · '}<span className="capitalize">{a.ticket_priority}</span> priority
                  </div>
                </div>
                <div className="text-xs text-slate-400 whitespace-nowrap ml-4">{new Date(a.created_at).toLocaleString()}</div>
              </div>

              <div className="text-xs mb-3">
                {a.is_final_stage ? (
                  <span className="text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">
                    Final approval — approving opens the ticket
                  </span>
                ) : (
                  <span className="text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                    Stage 1 of 2 — approving sends this to {a.requested_team_name || 'the target team'}'s admin
                  </span>
                )}
              </div>

              {error[a.id] && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-3">{error[a.id]}</div>}

              {a.is_final_stage && (
                <div className="mb-3">
                  <label className="block text-xs text-slate-600 mb-1">Assign to (optional — defaults to the requester)</label>
                  <select
                    value={assignee[a.id] || ''}
                    onChange={e => setAssignee({ ...assignee, [a.id]: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  >
                    <option value="">— default (requester) —</option>
                    {(teamMembers[a.current_team_id] || []).map(m => (
                      <option key={m.id} value={m.id}>{m.full_name} ({m.email})</option>
                    ))}
                  </select>
                </div>
              )}

              <input
                placeholder="Optional comment for the decision..."
                value={comment[a.id] || ''}
                onChange={e => setComment({ ...comment, [a.id]: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <div className="flex gap-2">
                <button onClick={() => decide(a.id, 'approve')}
                  className="px-3 py-1.5 text-sm bg-emerald-600 hover:bg-emerald-700 transition-colors duration-150 text-white rounded-lg">Approve</button>
                <button onClick={() => decide(a.id, 'reject')}
                  className="px-3 py-1.5 text-sm bg-white border border-rose-200 text-rose-600 hover:bg-rose-50 transition-colors duration-150 rounded-lg">Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
