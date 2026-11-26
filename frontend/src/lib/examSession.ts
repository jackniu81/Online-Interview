/**
 * Candidate exam session storage (design D4).
 *
 * Kept in sessionStorage: survives page refresh (so the countdown/progress do
 * not reset) but is tab-scoped, so two candidates on the same machine don't
 * share a session.
 */
import axios from 'axios'
import type { ExamStartResult } from './types'

const KEY = 'exam_session'
const LAST_LINK_KEY = 'exam_last_link'

export interface ExamSession {
  examId: number
  sessionToken: string
  linkToken: string
  questionCount: number
}

export function saveExamSession(s: ExamSession): void {
  sessionStorage.setItem(KEY, JSON.stringify(s))
  // survives hand-in clearing, so /exam/taking can bounce back to the real link
  sessionStorage.setItem(LAST_LINK_KEY, s.linkToken)
}

export function loadExamSession(): ExamSession | null {
  const raw = sessionStorage.getItem(KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ExamSession
  } catch {
    return null
  }
}

export function clearExamSession(): void {
  sessionStorage.removeItem(KEY)
}

export function getLastLinkToken(): string {
  return sessionStorage.getItem(LAST_LINK_KEY) ?? ''
}

export function sessionFromBegin(linkToken: string, r: ExamStartResult): ExamSession {
  return {
    examId: r.exam_id,
    sessionToken: r.session_token,
    linkToken,
    questionCount: r.question_count,
  }
}

/** Candidate-side axios instance; never carries the admin token. */
export const examApi = axios.create({ baseURL: '/api' })

export function examHeaders(): Record<string, string> {
  const s = loadExamSession()
  return s ? { Authorization: `Bearer ${s.sessionToken}` } : {}
}

export function apiErrorText(e: unknown, fallback = '操作失败，请重试'): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
  }
  return fallback
}
