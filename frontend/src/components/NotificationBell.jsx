import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const ref = useRef(null)
  const navigate = useNavigate()

  function loadCount() {
    api.get('/notifications/unread-count').then(({ data }) => setUnread(data.count)).catch(() => {})
  }

  function loadList() {
    api.get('/notifications').then(({ data }) => setItems(data)).catch(() => {})
  }

  useEffect(() => {
    loadCount()
    const interval = setInterval(loadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  function toggle() {
    if (!open) loadList()
    setOpen(!open)
  }

  async function handleClick(n) {
    if (!n.read) {
      await api.patch(`/notifications/${n.id}/read`)
      setItems(items.map(i => i.id === n.id ? { ...i, read: true } : i))
      setUnread(u => Math.max(0, u - 1))
    }
    if (n.ticket_id) {
      navigate(`/tickets/${n.ticket_id}`)
      setOpen(false)
    }
  }

  async function markAllRead() {
    await api.post('/notifications/read-all')
    setItems(items.map(i => ({ ...i, read: true })))
    setUnread(0)
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="relative w-9 h-9 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:bg-slate-800 transition-colors duration-150">
        <i className="ti ti-bell text-lg"></i>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-rose-500 text-white text-[10px] font-semibold flex items-center justify-center animate-soft-pulse">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-80 bg-white border border-slate-200 rounded-xl shadow-lg z-50 animate-modal overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <span className="text-sm font-medium text-slate-900">Notifications</span>
            {unread > 0 && (
              <button onClick={markAllRead} className="text-xs text-brand-600 hover:text-brand-700">Mark all read</button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-slate-400">
                <i className="ti ti-bell-off text-2xl text-slate-300 block mb-1"></i>
                Nothing yet.
              </div>
            ) : (
              items.map(n => (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors duration-150 flex gap-2 ${!n.read ? 'bg-brand-50/40' : ''}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${!n.read ? 'bg-brand-500' : 'bg-transparent'}`}></span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-slate-700 leading-snug">{n.message}</div>
                    {n.ticket_title && <div className="text-[11px] text-slate-400 mt-0.5 truncate">{n.ticket_title}</div>}
                    <div className="text-[11px] text-slate-400 mt-0.5">{timeAgo(n.created_at)}</div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
