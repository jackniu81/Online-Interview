import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import axios from 'axios'
import Markdown from '../components/Markdown'
import {
  apiErrorText,
  clearExamSession,
  examApi,
  examHeaders,
  getLastLinkToken,
  loadExamSession,
} from '../lib/examSession'
import { useBlockClipboard, QUESTION_AREA_STYLE } from '../lib/proctoring'
import type { CurrentQuestion } from '../lib/types'

function formatMMSS(seconds: number): string {
  const s = Math.max(0, seconds)
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

function statusOf(e: unknown): number | undefined {
  return axios.isAxiosError(e) ? e.response?.status : undefined
}

type Result = { why: 'last' | 'timeout' } | null

export default function ExamTaking() {
  // link token outlives the session (kept after hand-in clearing), so a stale
  // /exam/taking mount can bounce back to the real link instead of "链接无效"
  const [lostLinkToken] = useState(() => loadExamSession()?.linkToken ?? getLastLinkToken())
  const session = loadExamSession()
  const [question, setQuestion] = useState<CurrentQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [seconds, setSeconds] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<Result>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const finishedRef = useRef(false)
  useBlockClipboard(containerRef)

  // hand in on timeout; safe to call multiple times (server keeps one winner)
  const finishByTimeout = useCallback(async () => {
    if (finishedRef.current) return
    finishedRef.current = true
    try {
      await examApi.post('/exams/finish', {}, { headers: examHeaders() })
    } catch {
      /* server-side timer/lazy check will finish it anyway */
    }
    setResult({ why: 'timeout' })
  }, [])

  const loadQuestion = useCallback(async () => {
    try {
      const resp = await examApi.get<CurrentQuestion>('/exams/current-question', {
        headers: examHeaders(),
      })
      setQuestion(resp.data)
      setSeconds(resp.data.remaining_seconds)
      setError('')
    } catch (e) {
      if (statusOf(e) === 409) await finishByTimeout() // finished/timed out server-side
      else setError(apiErrorText(e, '题目加载失败，请刷新重试'))
    }
  }, [finishByTimeout])

  useEffect(() => {
    if (session) void loadQuestion()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadQuestion])

  // local ticking, started once; the server value re-syncs on every response
  useEffect(() => {
    if (result) return // stop ticking after hand-in so the result page is stable
    const t = setInterval(() => setSeconds((s) => (s === null ? s : Math.max(0, s - 1))), 1000)
    return () => clearInterval(t)
  }, [result, seconds === null])
  useEffect(() => {
    if (seconds === 0 && !result) void finishByTimeout()
  }, [seconds, result, finishByTimeout])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!question || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const resp = await examApi.post(
        '/exams/submit-answer',
        { sort_order: question.sort_order, answer_text: answer },
        { headers: examHeaders() },
      )
      const data = resp.data as { is_last: boolean }
      setAnswer('')
      if (data.is_last) setResult({ why: 'last' })
      else await loadQuestion()
    } catch (e) {
      if (statusOf(e) === 409) await finishByTimeout() // timed out -> auto-handed-in
      else setError(apiErrorText(e, '提交失败，请重试'))
    } finally {
      setSubmitting(false)
    }
  }

  // result first: SubmittedPage clears the session, which must not trigger the redirect
  if (result) {
    return <SubmittedPage result={result} />
  }
  // session lost (refresh after hand-in / cleared storage): go back to the link
  // so the entry page can show 已完成 or resume via re-registration
  if (!session) {
    return <Navigate to={`/exam?t=${encodeURIComponent(lostLinkToken)}`} replace />
  }

  return (
    <div ref={containerRef} style={{ maxWidth: 720, margin: '24px auto', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>在线考试</h2>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: seconds !== null && seconds <= 60 ? '#c0392b' : '#0b6bcb',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          剩余 {formatMMSS(seconds ?? 0)}
        </div>
      </div>
      <p style={{ color: '#555' }}>
        第 {question ? question.question_number : '-'} / {session.questionCount} 题
      </p>

      {question ? (
        <div
          style={{
            ...QUESTION_AREA_STYLE,
            border: '1px solid #ddd',
            borderRadius: 8,
            padding: 16,
            background: '#fafafa',
          }}
        >
          <Markdown content={question.question_content} />
        </div>
      ) : (
        !error && <p>题目加载中…</p>
      )}

      <form onSubmit={(e) => void onSubmit(e)}>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="请输入你的作答…"
          rows={10}
          disabled={result !== null}
          style={{ width: '100%', marginTop: 12, padding: 8, boxSizing: 'border-box' }}
        />
        {error && <p style={{ color: 'crimson' }}>{error}</p>}
        <button
          type="submit"
          disabled={!question || submitting}
          style={{ marginTop: 8, padding: '8px 24px', cursor: 'pointer' }}
        >
          {submitting
            ? '提交中…'
            : question && question.question_number === question.question_count
              ? '提交并交卷'
              : '提交下一题'}
        </button>
      </form>
    </div>
  )
}

function SubmittedPage({ result }: { result: NonNullable<Result> }) {
  useEffect(() => {
    clearExamSession()
  }, [])
  return (
    <div style={{ maxWidth: 520, margin: '120px auto', textAlign: 'center' }}>
      <h2>交卷成功</h2>
      <p>{result.why === 'timeout' ? '考试时间到，系统已自动交卷。' : '您已完成全部题目。'}</p>
      <p style={{ color: '#555' }}>答案将进入评分流程，结果以管理员通知为准。感谢您的参与！</p>
    </div>
  )
}
