import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setAdminToken } from '../lib/api'

export default function AdminLogin() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const resp = await api.post('/admin/login', { password })
      setAdminToken(resp.data.token)
      navigate('/admin/exams')
    } catch {
      setError('密码错误')
    }
  }

  return (
    <div style={{ maxWidth: 320, margin: '120px auto' }}>
      <h2>管理员登录</h2>
      <form onSubmit={onSubmit}>
        <input
          type="password"
          placeholder="请输入管理密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ width: '100%', padding: 8 }}
        />
        {error && <p style={{ color: 'crimson' }}>{error}</p>}
        <button type="submit" style={{ marginTop: 8, padding: '6px 16px' }}>
          登录
        </button>
      </form>
    </div>
  )
}
