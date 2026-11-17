export interface HistoryAttempt {
  attempt_id: number
  question_id: number
  concept_id: number
  attempted_at: string
  is_correct: boolean
  mastery_before: number | null
  mastery_after: number | null
  origin: 'ordinary_practice' | 'diagnostic' | 'adaptive_practice'
  snapshots_available: boolean
}

export interface LearningHistoryResponse {
  student_id: number
  concept_id: number | null
  attempts: HistoryAttempt[]
  next_cursor: string | null
}

export async function fetchHistory(
  studentId: number, conceptId: number, cursor: string | null = null, signal?: AbortSignal,
): Promise<LearningHistoryResponse> {
  const params = new URLSearchParams({ concept_id: String(conceptId), limit: '50' })
  if (cursor !== null) params.set('cursor', cursor)
  const response = await fetch(`http://127.0.0.1:8000/students/${studentId}/history?${params}`, {
    signal, cache: 'no-store',
  })
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : 'Could not load learning history. Please try again.')
  }
  return response.json()
}
