import type { ExamDisplayStatus } from './types'

export const STATUS_LABELS: Record<ExamDisplayStatus | string, string> = {
  incomplete: '未完成',
  grading: '评分中',
  excellent: '优秀',
  pass: '合格',
  fail: '不合格',
}

const STATUS_COLORS: Record<string, string> = {
  incomplete: '#888',
  grading: '#b8860b',
  excellent: '#1a7f37',
  pass: '#0b6bcb',
  fail: '#c0392b',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span style={{ color: STATUS_COLORS[status] ?? '#888', fontWeight: 600 }}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

/** Clipboard with execCommand fallback (dev server on plain http). */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through */
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(ta)
  return ok
}
