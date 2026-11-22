import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { setAdminToken } from '../lib/api'

export default function AdminLayout() {
  const navigate = useNavigate()

  function logout() {
    setAdminToken(null)
    navigate('/admin/login')
  }

  return (
    <div>
      <nav
        style={{
          display: 'flex',
          gap: 16,
          padding: '10px 24px',
          borderBottom: '1px solid #ddd',
          alignItems: 'center',
        }}
      >
        <strong>在线笔试系统</strong>
        <NavLink to="/admin/exams">面试人员</NavLink>
        <NavLink to="/admin/questions">题库</NavLink>
        <button onClick={logout} style={{ marginLeft: 'auto' }}>
          退出登录
        </button>
      </nav>
      <main style={{ padding: 24 }}>
        <Outlet />
      </main>
    </div>
  )
}
