import type { HistoryAttempt } from './api/history'

export interface MasteryPoint {
  attemptId: number
  order: number
  probability: number
  x: number
  y: number
}

export function masterySegments(attempts: HistoryAttempt[]): MasteryPoint[][] {
  const segments: MasteryPoint[][] = []
  let current: MasteryPoint[] | null = null
  attempts.forEach((attempt, index) => {
    const value = attempt.mastery_after
    if (value === null || !Number.isFinite(value) || value < 0 || value > 1) {
      current = null
      return
    }
    if (current === null) {
      current = []
      segments.push(current)
    }
    current.push({
      attemptId: attempt.attempt_id, order: index + 1, probability: value,
      x: attempts.length === 1 ? 336 : 56 + index * 560 / (attempts.length - 1),
      y: 192 - value * 168,
    })
  })
  return segments
}

export function historyPercentage(value: number | null): string {
  return value === null ? 'Not recorded' : `${(value * 100).toFixed(1)}%`
}
