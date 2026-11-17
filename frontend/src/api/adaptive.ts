import type { AttemptResponse } from './attempts'
import type { Question } from './questions'

export interface AdaptiveProgress {
  session_id: string; student_id: number; status: 'in_progress' | 'completed' | 'abandoned'
  created_at: string; updated_at: string; completed_at: string | null
  target_questions: number; assigned_questions: number; answered_questions: number
  next_position: number | null; next_question: Question | null
  selection_reason: string | null; current_question_eligible: boolean | null; blocked_reason: string | null
  completion_reason: 'target_reached' | 'eligible_pool_exhausted' | null
}
export interface AdaptiveAnswer { question_id: number; selected_answer: number; submission_id: string }
export interface AdaptiveFeedback { session_id: string; position: number; feedback: AttemptResponse }
export interface AdaptiveResults {
  session_id: string; student_id: number; status: 'completed'
  target_questions: number; answered_questions: number; correct_answers: number; accuracy: number | null
  completion_reason: 'target_reached' | 'eligible_pool_exhausted'
  questions: { position: number; question_id: number; concept_id: number; selection_reason: string; is_correct: boolean }[]
  mastery_basis: 'last_adaptive_attempt'
  concepts: { concept_id: number; concept_name: string; estimated_mastery: number | null
    status: 'weak' | 'learning' | 'mastered' | null; answered_questions: number }[]
}
export class AdaptiveError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
async function request<T>(student: number, path: string, signal?: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(`http://127.0.0.1:8000/students/${student}/adaptive-sessions${path}`, {
    method: body === undefined ? 'GET' : 'POST', signal, cache: 'no-store',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  })
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null)
    const detail = error && typeof error === 'object' && 'detail' in error ? error.detail : null
    throw new AdaptiveError(typeof detail === 'string' ? detail : 'Could not load the practice session. Please try again.', response.status)
  }
  return response.json()
}
export const adaptiveApi = {
  start: (student: number, signal?: AbortSignal) => request<AdaptiveProgress>(student, '/start', signal, {}),
  progress: (student: number, session: string, signal?: AbortSignal) => request<AdaptiveProgress>(student, `/${encodeURIComponent(session)}`, signal),
  answer: (student: number, session: string, body: AdaptiveAnswer, signal?: AbortSignal) => request<AdaptiveFeedback>(student, `/${encodeURIComponent(session)}/answers`, signal, body),
  results: (student: number, session: string, signal?: AbortSignal) => request<AdaptiveResults>(student, `/${encodeURIComponent(session)}/results`, signal),
  restart: (student: number, requestId: string, signal?: AbortSignal) => request<AdaptiveProgress>(student, '/restart', signal, { request_id: requestId }),
}
