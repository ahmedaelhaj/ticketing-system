import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

export default function Account() {
  const { user } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (newPassword !== confirmPassword) {
      setError("New passwords don't match.")
      return
    }

    setBusy(true)
    try {
      await api.patch('/users/me/password', { current_password: currentPassword, new_password: newPassword })
      setSuccess('Password updated.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not update password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto mt-4">
      <div className="mb-6 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-brand-50 text-brand-600 mb-3">
          <i className="ti ti-shield-lock text-2xl"></i>
        </div>
        <h1 className="text-xl font-medium text-slate-900">My account</h1>
        <p className="text-sm text-slate-500 mt-1">{user?.full_name} · {user?.email}</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6 animate-modal">
        <h2 className="text-sm font-medium text-slate-900 mb-4">Change password</h2>
        <form onSubmit={submit} className="space-y-4">
          {error && <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{error}</div>}
          {success && <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">{success}</div>}
          <div>
            <label className="block text-sm text-slate-700 mb-1">Current password</label>
            <input required type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">New password</label>
            <input required type="password" minLength={5} value={newPassword} onChange={e => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-sm text-slate-700 mb-1">Confirm new password</label>
            <input required type="password" minLength={5} value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <button disabled={busy} className="w-full px-4 py-2 text-sm bg-brand-600 hover:bg-brand-700 transition-colors duration-150 text-white rounded-lg disabled:opacity-60">
            {busy ? 'Updating...' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  )
}
