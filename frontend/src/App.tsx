import { Navigate, Route, Routes } from 'react-router-dom'
import { getAdminToken } from './lib/api'
import AdminExams from './pages/AdminExams'
import AdminLayout from './pages/AdminLayout'
import AdminLogin from './pages/AdminLogin'
import AdminQuestions from './pages/AdminQuestions'
import ExamEntry from './pages/ExamEntry'

function RequireAdmin({ children }: { children: React.ReactNode }) {
  if (!getAdminToken()) return <Navigate to="/admin/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin/exams" replace />} />
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route path="exams" element={<AdminExams />} />
        <Route path="exams/:id" element={<AdminExams />} />
        <Route path="questions" element={<AdminQuestions />} />
      </Route>
      <Route path="/exam" element={<ExamEntry />} />
    </Routes>
  )
}
