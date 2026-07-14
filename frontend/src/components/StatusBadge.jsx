const STYLES = {
  pending_approval: 'bg-amber-100 text-amber-800',
  open: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-indigo-100 text-indigo-800',
  closed: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-rose-100 text-rose-800',
}

const LABELS = {
  pending_approval: 'Pending approval',
  open: 'Open',
  in_progress: 'In progress',
  closed: 'Closed',
  rejected: 'Rejected',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors duration-200 ${STYLES[status] || 'bg-slate-100 text-slate-700'}`}>
      {status === 'pending_approval' && <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-soft-pulse"></span>}
      {LABELS[status] || status}
    </span>
  )
}
