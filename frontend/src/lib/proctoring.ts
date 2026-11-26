import { useEffect } from 'react'
import type { RefObject } from 'react'

/**
 * Best-effort exam proctoring deterrent (task 7.3, design D8): blocks
 * copy/cut/paste/contextmenu inside the container and via keyboard shortcuts
 * (Ctrl/Cmd + C/V/X). Not adversarial-proof — paired with recording.
 */
export function useBlockClipboard(containerRef: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const block = (e: Event) => e.preventDefault()
    const events = ['copy', 'cut', 'paste', 'contextmenu'] as const
    events.forEach((ev) => el.addEventListener(ev, block))

    function onKeydown(e: KeyboardEvent) {
      if (!(e.ctrlKey || e.metaKey)) return
      if (['c', 'v', 'x'].includes(e.key.toLowerCase())) e.preventDefault()
    }
    document.addEventListener('keydown', onKeydown)
    return () => {
      events.forEach((ev) => el.removeEventListener(ev, block))
      document.removeEventListener('keydown', onKeydown)
    }
  }, [containerRef])
}

export const QUESTION_AREA_STYLE = { userSelect: 'none' as const }
