import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { copyText, StatusBadge } from '../lib/examui'
import type { ExamListItem, ExamCreateResult, Page } from '../lib/types'

const inputStyle: React.CSSProperties = {
  padding: 8,
  boxSizing: 'border-box',
}

const COUNT_OPTIONS = [5, 10, 15, 20]
const DURATION_OPTIONS = [15, 20, 30, 40]
const STATUS_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'incomplete', label: '未完成' },
  { value: 'grading', label: '评分中' },
  { value: 'excellent', label: '优秀' },
  { value: 'pass', label: '合格' },
  { value: 'fail', label: '不合格' },
]
const DAY_OPTIONS = [
  { value: 7, label: '近 1 周' },
  { value: 30, label: '近 1 个月' },
  { value: 90, label: '近 3 个月' },
  { value: 365, label: '近 1 年' },
]

export default function AdminExams() {
  const [email, setEmail] = useState('')
  const [questionCount, setQuestionCount] = useState(5)
  const [duration, setDuration] = useState(15)
  const [created, setCreated] = useState<ExamCreateResult | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [copied, setCopied] = useState('')

  const [status, setStatus] = useState('all')
  const [days, setDays] = useState(7)
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Page<ExamListItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
  })

  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    const resp = await api.get('/admin/exams', {
      params: { status, days, page, page_size: PAGE_SIZE },
    })
    setData(resp.data)
  }, [status, days, page])

  useEffect(() => {
    load().catch(() => {})
  }, [load])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setCreating(true)
    setCreateError('')
    setCreated(null)
    try {
      const resp = await api.post('/admin/exams', {
        email,
        question_count: questionCount,
        duration_minutes: duration,
      })
      setCreated(resp.data)
      setEmail('')
      await load()
    } catch (err: any) {
      const d = err.response?.data?.detail
      setCreateError(typeof d === 'string' ? d : Array.isArray(d) ? d[0]?.msg ?? '参数有误' : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  async function onCopy(link: string) {
    setCopied((await copyText(link)) ? '已复制' : '复制失败，请手动选择链接')
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>创建考试</h2>
      <form onSubmit={onCreate} style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
        <input
          type="email"
          required
          placeholder="候选人邮箱 *"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ ...inputStyle, width: 260 }}
        />
        <label>
          题数{' '}
          <select value={questionCount} onChange={(e) => setQuestionCount(Number(e.target.value))}>
            {COUNT_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n} 题
              </option>
            ))}
          </select>
        </label>
        <label>
          时长{' '}
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            {DURATION_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n} 分钟
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={creating}>
          {creating ? '创建中…' : '创建并生成链接'}
        </button>
      </form>
      {createError && <p style={{ color: 'crimson' }}>{createError}</p>}
      {created && (
        <div style={{ border: '1px solid #1a7f37', borderRadius: 6, padding: 12, marginBottom: 16, background: '#f2fbf5' }}>
          <div>
            考试链接（发送给 {created.email}）：
            <code style={{ wordBreak: 'break-all', fontSize: 12 }}> {created.link}</code>
          </div>
          <div style={{ marginTop: 8 }}>
            <button onClick={() => onCopy(created.link)}>复制链接</button>{' '}
            {copied && <span style={{ color: '#1a7f37' }}>{copied}</span>}
          </div>
        </div>
      )}

      <h2>考试列表</h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <label>
          状态{' '}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          创建时间{' '}
          <select
            value={days}
            onChange={(e) => {
              setDays(Number(e.target.value))
              setPage(1)
            }}
          >
            {DAY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <table border={1} cellSpacing={0} cellPadding={8} style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ width: 60 }}>ID</th>
            <th>邮箱</th>
            <th>姓名</th>
            <th style={{ width: 60 }}>题数</th>
            <th style={{ width: 60 }}>时长</th>
            <th style={{ width: 170 }}>创建时间</th>
            <th style={{ width: 170 }}>完成时间</th>
            <th style={{ width: 70 }}>总分</th>
            <th style={{ width: 80 }}>状态</th>
            <th style={{ width: 70 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.email}</td>
              <td>{item.candidate_name ?? '-'}</td>
              <td>{item.question_count}</td>
              <td>{item.duration_minutes}</td>
              <td>{new Date(item.created_at).toLocaleString()}</td>
              <td>{item.completed_at ? new Date(item.completed_at).toLocaleString() : '-'}</td>
              <td>{item.total_score ?? '-'}</td>
              <td>
                <StatusBadge status={item.status} />
              </td>
              <td>
                <Link to={`/admin/exams/${item.id}`}>明细</Link>
              </td>
            </tr>
          ))}
          {data.items.length === 0 && (
            <tr>
              <td colSpan={10} style={{ textAlign: 'center', color: '#888' }}>
                暂无考试记录
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div style={{ marginTop: 8, color: '#666' }}>
        共 {data.total} 条 · 第 {data.page} 页{' '}
        <button disabled={data.page <= 1} onClick={() => setPage(data.page - 1)}>
          上一页
        </button>{' '}
        <button disabled={data.page * PAGE_SIZE >= data.total} onClick={() => setPage(data.page + 1)}>
          下一页
        </button>
      </div>
    </div>
  )
}
