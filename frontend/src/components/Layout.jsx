import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationBell from './NotificationBell'

const ICONS = {
  dashboard: 'ti-layout-dashboard',
  tickets: 'ti-ticket',
  approvals: 'ti-checklist',
  reports: 'ti-report',
  users: 'ti-users',
  teams: 'ti-building',
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const links = [
    { to: '/', label: 'Dashboard', icon: ICONS.dashboard, roles: ['normal_user', 'team_admin', 'super_admin'] },
    { to: '/tickets', label: 'Tickets', icon: ICONS.tickets, roles: ['normal_user', 'team_admin', 'super_admin'] },
    { to: '/approvals', label: 'Approvals', icon: ICONS.approvals, roles: ['team_admin', 'super_admin'] },
    { to: '/reports', label: 'Reports', icon: ICONS.reports, roles: ['normal_user', 'team_admin', 'super_admin'] },
    { to: '/teams', label: 'Teams', icon: ICONS.teams, roles: ['super_admin'] },
    { to: '/users', label: 'Users', icon: ICONS.users, roles: ['super_admin'] },
  ]

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-60 shrink-0 bg-slate-900 text-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <div className="text-white font-medium text-lg">SME Ticketing</div>
            <div className="text-xs text-slate-400 mt-0.5">internal task management</div>
          </div>
          <NotificationBell />
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {links.filter(l => l.roles.includes(user?.role)).map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${
                  isActive ? 'bg-brand-600 text-white' : 'hover:bg-slate-800 text-slate-300'
                }`
              }
            >
              <i className={`ti ${l.icon} text-base`}></i>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-slate-800">
          <div className="text-sm text-white">{user?.full_name}</div>
          <div className="text-xs text-slate-400 capitalize mb-3">{user?.role?.replace('_', ' ')}</div>
          <NavLink to="/account" className="text-xs text-slate-400 hover:text-white flex items-center gap-1 mb-2">
            <i className="ti ti-user-cog"></i> My account
          </NavLink>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
          >
            <i className="ti ti-logout"></i> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <div key={location.pathname} className="max-w-6xl mx-auto px-8 py-8 animate-page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
