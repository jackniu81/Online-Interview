import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Markdown from '../components/Markdown'
import { api } from '../lib/api'
import { StatusBadge } from '../lib/examui'
import type { ExamDetail } from '../lib/types'

const GRADING_LABELS: Record<string, string> = {
  unanswered: '未作答',
  pending: '评分中',
  grading: '评分中',
  graded: '已评分',
  failed: '评分失败',
}

export default function AdminExamDetail() {
  const { id } = useParams()
  const [exam, setExam] = useState<ExamDetail | null>(null)
  const [error, setError] = useState('')
  const [refreshedAt, setRefreshedAt] = useState('')

  const load = useCallback(async () => {
    try {
      const resp = await api.get(`/admin/exams/${id}`)
      setExam(resp.data)
      setRefreshedAt(new Date().toLocaleTimeString())
      setError('')
      return resp.data.status as string
    } catch (err: any) {
      setError(err.response?.status === 404 ? '考试不存在' : '加载失败')
      return ''
    }
  }, [id])

  // 评分中时每 5 秒自动刷新，直至全部终态
  useEffect(() => {
    let timer: number | undefined
    let stopped = false
    async function tick() {
      const st = await load()
      if (!stopped && st === 'grading') timer = window.setTimeout(tick, 5000)
    }
    tick()
    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
    }
  }, [load])

  if (error) return <p style={{ color: 'crimson' }}>{error}</p>
  if (!exam) return <p>加载中…</p>

  return (
    <div>
      <p>
        <Link to="/admin/exams">← 返回列表</Link>
      </p>
      <h2 style={{ marginTop: 0 }}>
        考试 #{exam.id} <StatusBadge status={exam.status} />
      </h2>

      <table cellSpacing={0} cellPadding={6} style={{ borderCollapse: 'collapse', marginBottom: 16 }}>
        <tbody>
          <tr>
            <td>邮箱</td>
            <td>{exam.email}</td>
            <td>姓名</td>
            <td>{exam.candidate_name ?? '-'}</td>
            <td>电话</td>
            <td>{exam.candidate_phone ?? '-'}</td>
          </tr>
          <tr>
            <td>题数 / 时长</td>
            <td>{exam.question_count} 题 / {exam.duration_minutes} 分钟</td>
            <td>创建时间</td>
            <td>{new Date(exam.created_at).toLocaleString()}</td>
            <td>完成时间</td>
            <td>{exam.completed_at ? new Date(exam.completed_at).toLocaleString() : '-'}</td>
          </tr>
          <tr>
            <td>总分</td>
            <td>{exam.total_score ?? '-'}</td>
            <td colSpan={3}>
              {exam.status === 'grading' && (
                <>
                  <button onClick={() => load()}>手动刷新</button>
                  <span style={{ color: '#888', marginLeft: 8 }}>评分中，每 5 秒自动刷新（{refreshedAt}）</span>
                </>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      {exam.questions.map((q) => (
        <div key={q.sort_order} style={{ border: '1px solid #ddd', borderRadius: 6, padding: 12, marginBottom: 12 }}>
          <h4 style={{ marginTop: 0 }}>
            {q.sort_order + 1}. {' '}
            <span
              style={{
                fontSize: 12,
                color: q.grading_status === 'failed' ? '#c0392b' : q.grading_status === 'graded' ? '#1a7f37' : '#888',
                marginLeft: 6,
              }}
            >
              {GRADING_LABELS[q.grading_status] ?? q.grading_status}
            </span>
            {q.score !== null && <span style={{ marginLeft: 8 }}>得分：{q.score}</span>}
          </h4>
          <Markdown content={q.question_content} />
          <div style={{ borderTop: '1px dashed #ccc', margin: '10px 0', paddingTop: 10 }}>
            <strong>候选人作答：</strong>
            {q.answer_text ? <Markdown content={q.answer_text} /> : <span style={{ color: '#888' }}>（未作答）</span>}
          </div>
          {q.feedback && (
            <div style={{ background: '#f6f8fa', padding: 8, borderRadius: 4 }}>
              <strong>AI 评价：</strong>
              <Markdown content={q.feedback} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
