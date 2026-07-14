import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

const NEXT_ACTIONS = {
  open: [{ to: 'in_progress', label: 'Start progress', dynamicCheck: 'canStartProgress' }],
  in_progress: [{ to: 'closed', label: 'Close ticket' }],
  closed: [{ to: 'open', label: 'Reopen ticket', restrictedTo: ['team_admin', 'super_admin'] }],
  rejected: [{ to: 'pending_approval', label: 'Resubmit for approval' }],
}

const STATUS_DOT = {
  pending_approval: 'bg-amber-500',
  open: 'bg-blue-500',
  in_progress: 'bg-indigo-500',
  closed: 'bg-emerald-500',
  rejected: 'bg-rose-500',
}

const STATUS_PILL = {
  pending_approval: 'bg-amber-50 text-amber-700',
  open: 'bg-blue-50 text-blue-700',
  in_progress: 'bg-indigo-50 text-indigo-700',
  closed: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-rose-50 text-rose-700',
}

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
  return closedIso ? label : `${label} so far`
}

function timeAgo(iso) {
  if (!iso) return ''
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatBytes(n) {
  if (!n && n !== 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function TicketDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState(null)
  const [comments, setComments] = useState([])
  const [history, setHistory] = useState([])
  const [attachments, setAttachments] = useState([])
  const [approvals, setApprovals] = useState([])
  const [commentBody, setCommentBody] = useState('')
  const [showRedirect, setShowRedirect] = useState(false)
  const [error, setError] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)

  function load() {
    api.get(`/tickets/${id}`).then(({ data }) => setTicket(data))
    api.get(`/tickets/${id}/comments`).then(({ data }) => setComments(data))
    api.get(`/tickets/${id}/history`).then(({ data }) => setHistory(data))
    api.get(`/tickets/${id}/attachments`).then(({ data }) => setAttachments(data))
    api.get(`/tickets/${id}/approvals`).then(({ data }) => setApprovals(data))
  }

  useEffect(load, [id])

  async function changeStatus(newStatus) {
    setError('')
    try {
      const { data } = await api.patch(`/tickets/${id}/status`, { status: newStatus })
      setTicket(data)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update status.')
    }
  }

  async function deleteTicket() {
    if (!confirm('Permanently delete this ticket? This cannot be undone.')) return
    setError('')
    try {
      await api.delete(`/tickets/${id}`)
      navigate('/tickets')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete this ticket.')
    }
  }

  async function submitComment(e) {
    e.preventDefault()
    if (!commentBody.trim()) return
    const { data } = await api.post(`/tickets/${id}/comments`, { body: commentBody })
    setComments([...comments, data])
    setCommentBody('')
  }

  async function uploadFiles(fileList) {
    setUploadBusy(true)
    setError('')
    try {
      for (const file of Array.from(fileList)) {
        const form = new FormData()
        form.append('file', file)
        await api.post(`/tickets/${id}/attachments`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      }
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not upload file.')
    } finally {
      setUploadBusy(false)
    }
  }

  async function deleteAttachment(attachmentId) {
    if (!confirm('Remove this attachment?')) return
    await api.delete(`/attachments/${attachmentId}`)
    load()
  }

  async function downloadAttachment(a) {
    const res = await api.get(`/attachments/${a.id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', a.filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  if (!ticket) return <div className="text-sm text-slate-500">Loading...</div>

  const pendingApproval = approvals.find(a => a.decision === 'pending')
  const isApprover = pendingApproval && (user.id === pendingApproval.approver_id || user.role === 'super_admin')
  const isRequesterPending = user.id === ticket.created_by && ticket.status === 'pending_approval'

  const canStartProgress = user.role === 'super_admin'
    || user.id === ticket.assigned_to
    || (user.role === 'team_admin' && user.team_id === ticket.team_id)

  const canDeleteAlways = user.role === 'super_admin'

  const stage1Approvals = approvals.filter(a => a.stage === 1)
  const stage2Approvals = approvals.filter(a => a.stage === 2)
  const stage1 = stage1Approvals[stage1Approvals.length - 1]
  const stage2 = stage2Approvals[stage2Approvals.length - 1]
  const isCrossTeamTicket = !!ticket.requested_team_id || (ticket.origin_team_id && ticket.origin_team_id !== ticket.team_id)

  function approvalLabel(approval) {
    if (!approval) return null
    if (approval.decision === 'approve') return `${approval.approver_name} — approved`
    if (approval.decision === 'reject') return `${approval.approver_name} — rejected`
    return `${approval.approver_name} — pending`
  }

  const stage1Label = approvalLabel(stage1) || '—'
  const stage2Label = stage2 ? approvalLabel(stage2)
    : isCrossTeamTicket ? 'Awaiting 1st approval' : 'Not required (same team)'

  const actions = (NEXT_ACTIONS[ticket.status] || [])
    .filter(a => !a.restrictedTo || a.restrictedTo.includes(user.role))
    .filter(a => a.dynamicCheck !== 'canStartProgress' || canStartProgress)

  return (
    <div className="max-w-3xl">
      <Link to="/tickets" className="text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1 mb-4">
        <i className="ti ti-arrow-left"></i> Back to tickets
      </Link>

      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <div className="flex items-start justify-between mb-3">
          <h1 className="text-lg font-medium text-slate-900">{ticket.title}</h1>
          <StatusBadge status={ticket.status} />
        </div>
        <p className="text-sm text-slate-600 whitespace-pre-wrap mb-4">{ticket.description || 'No description provided.'}</p>

        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs text-slate-500 mb-5 bg-slate-50 rounded-lg p-4">
          <div><span className="text-slate-400 block mb-0.5">Priority</span><span className="capitalize text-slate-700">{ticket.priority}</span></div>
          <div>
            <span className="text-slate-400 block mb-0.5">Team</span>
            <span className="text-slate-700">
              {ticket.origin_team_name && ticket.origin_team_name !== ticket.team_name
                ? `${ticket.origin_team_name} → ${ticket.team_name}`
                : (ticket.team_name || '—')}
              {ticket.requested_team_name && <span className="text-amber-600"> → pending: {ticket.requested_team_name}</span>}
            </span>
          </div>

          <div><span className="text-slate-400 block mb-0.5">Created by</span><span className="text-slate-700">{ticket.created_by_name || '—'}</span></div>
          <div><span className="text-slate-400 block mb-0.5">Assign to</span><span className="text-slate-700">{ticket.assigned_to_name || '— unassigned —'}</span></div>

          <div><span className="text-slate-400 block mb-0.5">1st approved by</span><span className="text-slate-700">{stage1Label}</span></div>
          <div><span className="text-slate-400 block mb-0.5">2nd approved by</span><span className="text-slate-700">{stage2Label}</span></div>

          <div><span className="text-slate-400 block mb-0.5">Created</span><span className="text-slate-700">{formatDateTime(ticket.created_at)}</span></div>
          <div><span className="text-slate-400 block mb-0.5">Closed</span><span className="text-slate-700">{ticket.closed_at ? `${formatDateTime(ticket.closed_at)}${ticket.closed_by_name ? ` by ${ticket.closed_by_name}` : ''}` : '—'}</span></div>

          <div className="col-span-2"><span className="text-slate-400 block mb-0.5">Duration</span><span className="text-slate-700">{formatDuration(ticket.created_at, ticket.closed_at)}</span></div>
        </div>

        {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-4">{error}</div>}

        <div className="flex flex-wrap gap-2">
          {actions.map(a => (
            <button key={a.to} onClick={() => changeStatus(a.to)}
              className="px-3 py-1.5 text-sm bg-slate-900 text-white rounded-lg hover:bg-slate-800">
              {a.label}
            </button>
          ))}
          {ticket.status !== 'pending_approval' && (
            <button onClick={() => setShowRedirect(true)}
              className="px-3 py-1.5 text-sm bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50">
              Redirect
            </button>
          )}
          {canDeleteAlways && (
            <button onClick={deleteTicket}
              className="px-3 py-1.5 text-sm bg-white border border-rose-200 text-rose-600 rounded-lg hover:bg-rose-50 ml-auto">
              Delete
            </button>
          )}
        </div>
      </div>

      {isRequesterPending && (
        <div className="bg-white border border-rose-200 rounded-xl p-5 mb-6 flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-900">This ticket is still awaiting approval</div>
            <div className="text-xs text-slate-500 mt-0.5">You can delete it now, before it's decided. Once approved or rejected, this option goes away.</div>
          </div>
          <button onClick={deleteTicket}
            className="px-4 py-2 text-sm bg-rose-600 hover:bg-rose-700 transition-colors duration-150 text-white rounded-lg whitespace-nowrap">
            Delete ticket
          </button>
        </div>
      )}

      {isApprover && pendingApproval && (
        <ApprovalCard approval={pendingApproval} onDecided={load} />
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <h2 className="text-sm font-medium text-slate-900 mb-1">Ticket timeline</h2>
        <p className="text-xs text-slate-500 mb-4">Every step this ticket has been through, in order.</p>
        {history.length === 0 ? (
          <p className="text-sm text-slate-400">No activity yet.</p>
        ) : (
          <div className="space-y-0">
            {history.map((h, i) => (
              <div key={h.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className={`w-3 h-3 rounded-full mt-1 ring-4 ring-white ${STATUS_DOT[h.to_status] || 'bg-slate-400'}`}></div>
                  {i < history.length - 1 && <div className="w-px flex-1 bg-slate-200 my-0.5"></div>}
                </div>
                <div className="pb-5 flex-1">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded ${STATUS_PILL[h.to_status] || 'bg-slate-100 text-slate-600'}`}>
                      {h.to_status.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-slate-400">{timeAgo(h.changed_at)} · {formatDateTime(h.changed_at)}</span>
                  </div>
                  <div className="text-sm text-slate-800">
                    {h.note || <span>Status changed by {h.changed_by_name || 'unknown'}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <h2 className="text-sm font-medium text-slate-900 mb-4">Attachments</h2>
        {attachments.length === 0 ? (
          <p className="text-sm text-slate-400 mb-4">No files attached yet.</p>
        ) : (
          <div className="space-y-2 mb-4">
            {attachments.map(a => (
              <div key={a.id} className="flex items-center justify-between text-sm border border-slate-100 rounded-lg px-3 py-2">
                <button onClick={() => downloadAttachment(a)} className="flex items-center gap-2 text-slate-800 hover:text-brand-600 text-left">
                  <i className="ti ti-paperclip text-slate-400"></i>
                  <span className="font-medium">{a.filename}</span>
                  <span className="text-xs text-slate-400">{formatBytes(a.size_bytes)}</span>
                </button>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400">by {a.uploaded_by_name || 'unknown'} · {formatDateTime(a.created_at)}</span>
                  <button onClick={() => deleteAttachment(a.id)} className="text-rose-500 hover:text-rose-700 text-xs">Remove</button>
                </div>
              </div>
            ))}
          </div>
        )}
        <input type="file" multiple disabled={uploadBusy} onChange={e => e.target.files.length && uploadFiles(e.target.files)}
          className="w-full text-sm text-slate-600 file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700 file:text-sm hover:file:bg-slate-200 disabled:opacity-50" />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <h2 className="text-sm font-medium text-slate-900 mb-4">Comments</h2>
        <div className="space-y-3 mb-4">
          {comments.length === 0 && <p className="text-sm text-slate-400">No comments yet.</p>}
          {comments.map(c => (
            <div key={c.id} className="text-sm border-b border-slate-100 pb-3 last:border-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-[10px] font-semibold flex items-center justify-center">
                  {(c.author_name || '?').charAt(0).toUpperCase()}
                </span>
                <span className="text-xs font-medium text-slate-700">{c.author_name || 'Unknown user'}</span>
                <span className="text-xs text-slate-400">{formatDateTime(c.created_at)}</span>
              </div>
              <div className="text-slate-800 pl-7">{c.body}</div>
            </div>
          ))}
        </div>
        <form onSubmit={submitComment} className="flex gap-2">
          <input value={commentBody} onChange={e => setCommentBody(e.target.value)}
            placeholder="Add a comment..."
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          <button className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg">Post</button>
        </form>
      </div>

      {showRedirect && (
        <RedirectModal ticketId={id} currentTeamId={ticket.team_id}
          onClose={() => setShowRedirect(false)} onDone={() => { setShowRedirect(false); load() }} />
      )}
    </div>
  )
}

function ApprovalCard({ approval, onDecided }) {
  const [comment, setComment] = useState('')
  const [assignee, setAssignee] = useState('')
  const [members, setMembers] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (approval.is_final_stage && approval.current_team_id) {
      api.get(`/users/team/${approval.current_team_id}`).then(({ data }) => setMembers(data)).catch(() => setMembers([]))
    }
  }, [approval.is_final_stage, approval.current_team_id])

  async function decide(decision) {
    setBusy(true)
    setError('')
    try {
      await api.post(`/approvals/${approval.id}/decide`, {
        decision, comment: comment || '', assigned_to: assignee || null,
      })
      onDecided()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not record decision.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white border border-amber-200 rounded-xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <i className="ti ti-clock-hour-4 text-amber-500"></i>
        <h2 className="text-sm font-medium text-slate-900">Your approval is needed</h2>
      </div>
      <p className="text-xs text-slate-500 mb-4">
        {approval.is_final_stage
          ? 'Approving this opens the ticket immediately — pick who it should go to.'
          : `Approving this forwards it to ${approval.requested_team_name || 'the target team'}'s admin for final approval.`}
      </p>

      {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-3">{error}</div>}

      {approval.is_final_stage && (
        <div className="mb-3">
          <label className="block text-xs text-slate-600 mb-1">Assign to (optional — defaults to the requester)</label>
          <select value={assignee} onChange={e => setAssignee(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="">— default (requester) —</option>
            {members.map(m => <option key={m.id} value={m.id}>{m.full_name} ({m.email})</option>)}
          </select>
        </div>
      )}

      <input
        placeholder="Optional comment for the decision..."
        value={comment}
        onChange={e => setComment(e.target.value)}
        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      <div className="flex gap-2">
        <button disabled={busy} onClick={() => decide('approve')}
          className="px-3 py-1.5 text-sm bg-emerald-600 hover:bg-emerald-700 transition-colors duration-150 text-white rounded-lg disabled:opacity-60">Approve</button>
        <button disabled={busy} onClick={() => decide('reject')}
          className="px-3 py-1.5 text-sm bg-white border border-rose-200 text-rose-600 hover:bg-rose-50 transition-colors duration-150 rounded-lg disabled:opacity-60">Reject</button>
      </div>
    </div>
  )
}

function RedirectModal({ ticketId, currentTeamId, onClose, onDone }) {
  const [teams, setTeams] = useState([])
  const [members, setMembers] = useState([])
  const [teamId, setTeamId] = useState(currentTeamId || '')
  const [assignedTo, setAssignedTo] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/teams').then(({ data }) => setTeams(data))
  }, [])

  useEffect(() => {
    if (!teamId) { setMembers([]); return }
    api.get(`/users/team/${teamId}`).then(({ data }) => setMembers(data)).catch(() => setMembers([]))
  }, [teamId])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post(`/tickets/${ticketId}/redirect`, {
        assigned_to: assignedTo,
        team_id: teamId !== currentTeamId ? teamId : null,
      })
      onDone()
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not redirect ticket.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4 animate-backdrop">
      <div className="bg-white rounded-xl w-full max-w-md p-6 animate-modal">
        <h2 className="text-lg font-medium text-slate-900 mb-2">Redirect ticket</h2>
        <p className="text-xs text-slate-500 mb-4">This resets the ticket to Pending approval under the new owner's manager.</p>
        <form onSubmit={submit} className="space-y-4">
          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{error}</div>}
          <div>
            <label className="block text-sm text-slate-700 mb-1">Team</label>
            <select value={teamId} onChange={e => { setTeamId(e.target.value); setAssignedTo('') }}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="">Select a team</option>
              {teams.filter(t => t.is_active || t.id === currentTeamId).map(t => (
                <option key={t.id} value={t.id}>{t.name}{t.id === currentTeamId ? ' (current)' : ''}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">New assignee</label>
            <select required value={assignedTo} onChange={e => setAssignedTo(e.target.value)} disabled={!teamId}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50">
              <option value="">{teamId ? 'Select a person' : 'Pick a team first'}</option>
              {members.map(m => <option key={m.id} value={m.id}>{m.full_name} ({m.email})</option>)}
            </select>
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
            <button disabled={busy} className="px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg disabled:opacity-60">
              {busy ? 'Redirecting...' : 'Redirect'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
