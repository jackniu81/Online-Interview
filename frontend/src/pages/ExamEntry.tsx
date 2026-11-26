import { FormEvent, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import axios from 'axios'
import { apiErrorText, examApi, saveExamSession, sessionFromBegin } from '../lib/examSession'
import { useBlockClipboard, QUESTION_AREA_STYLE } from '../lib/proctoring'
import type { ExamInfoResponse, ExamStartResult } from '../lib/types'

type View =
  | { kind: 'loading' }
  | { kind: 'invalid' }
  | { kind: 'completed' }
  | { kind: 'register'; info: ExamInfoResponse }

export default function ExamEntry() {
  const [params] = useSearchParams()
  const linkToken = params.get('t') ?? ''
  const [view, setView] = useState<View>({ kind: 'loading' })
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  useBlockClipboard(containerRef)

  // resolve the link once on mount
  useEffect(() => {
    void (async () => {
      if (!linkToken) {
        setView({ kind: 'invalid' })
        return
      }
      try {
        const resp = await examApi.get<ExamInfoResponse>('/exams/info', {
          params: { t: linkToken },
        })
        if (resp.data.completed) {
          setView({ kind: 'completed' })
          return
        }
        // started but session storage was cleared: the candidate re-registers
        // (begin is idempotent server-side and keeps the original deadline)
        setView({ kind: 'register', info: resp.data })
      } catch {
        setView({ kind: 'invalid' })
      }
    })()
  }, [linkToken])

  async function onStart(e: FormEvent) {
    e.preventDefault()
    setError('')
    const trimmed = name.trim()
    if (!trimmed) {
      setError('请输入姓名')
      return
    }
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      setError('请输入正确的 11 位手机号')
      return
    }
    try {
      const resp = await examApi.post<ExamStartResult>('/exams/begin', {
        token: linkToken,
        name: trimmed,
        phone,
      })
      saveExamSession(sessionFromBegin(linkToken, resp.data))
      window.location.href = '/exam/taking'
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined
      if (status === 404) setView({ kind: 'invalid' })
      else if (status === 409) setView({ kind: 'completed' })
      else setError(apiErrorText(err, '开始考试失败，请重试'))
    }
  }

  return (
    <div ref={containerRef} style={{ maxWidth: 560, margin: '60px auto', padding: 16 }}>
      {view.kind === 'loading' && <p>正在验证考试链接…</p>}

      {view.kind === 'invalid' && (
        <div>
          <h2>链接无效</h2>
          <p>考试链接不正确或已失效，请向主办方确认。</p>
          <Link to="/admin/exams">返回</Link>
        </div>
      )}

      {view.kind === 'completed' && (
        <div>
          <h2>考试已完成</h2>
          <p>该考试已交卷，不能重复作答。感谢您的参与！</p>
        </div>
      )}

      {view.kind === 'register' && (
        <div>
          <h2>在线考试信息登记</h2>
          <div
            style={{ ...QUESTION_AREA_STYLE, border: '1px solid #ddd', borderRadius: 8, padding: 16, background: '#fafafa' }}
          >
            <p>
              题目数：<strong>{view.info.question_count}</strong> 题
            </p>
            <p>
              考试时长：<strong>{view.info.duration_minutes}</strong> 分钟
            </p>
            <ul style={{ color: '#555' }}>
              <li>开始答题后倒计时不可暂停，刷新页面不会重置计时。</li>
              <li>每页仅显示 1 题，提交后进入下一题，已提交题目不可回退或修改。</li>
              <li>考试时间归零将自动交卷，未答题按空答案处理。</li>
              <li>答题过程禁止复制、剪切、粘贴与右键，请勿尝试。</li>
            </ul>
          </div>
          <form onSubmit={onStart} style={{ marginTop: 16 }}>
            <input
              placeholder="姓名"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ width: '100%', padding: 8, marginBottom: 8, boxSizing: 'border-box' }}
            />
            <input
              placeholder="手机号"
              value={phone}
              maxLength={11}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
              style={{ width: '100%', padding: 8, boxSizing: 'border-box' }}
            />
            {error && <p style={{ color: 'crimson' }}>{error}</p>}
            <button
              type="submit"
              style={{ marginTop: 12, padding: '8px 24px', cursor: 'pointer' }}
            >
              开始考试
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
