import type { AttemptResponse } from './attempts'
import type { Question } from './questions'

export interface DiagnosticProgress {
  session_id: string; student_id: number; status: 'in_progress' | 'completed' | 'abandoned'
  created_at: string; updated_at: string; completed_at: string | null
  total_questions: number; answered_questions: number
  next_position: number | null; next_question: Question | null
}
export interface DiagnosticAnswer { question_id: number; selected_answer: number; submission_id: string }
export interface DiagnosticFeedback { session_id: string; position: number; feedback: AttemptResponse }
export interface DiagnosticResults {
  session_id: string; student_id: number; status: 'completed'
  total_questions: number; answered_questions: number; correct_answers: number; accuracy: number
  mastery_basis: 'last_diagnostic_attempt'
  concepts: { concept_id: number; concept_name: string; estimated_mastery: number | null
    status: 'weak' | 'learning' | 'mastered' | null; answered_questions: number }[]
}
export class DiagnosticError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}
async function request<T>(student: number, path: string, signal?: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(`http://127.0.0.1:8000/students/${student}/diagnostics${path}`, {
    method: body === undefined ? 'GET' : 'POST', signal, cache: 'no-store',
    ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  })
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null)
    const detail = error && typeof error === 'object' && 'detail' in error ? error.detail : null
    throw new DiagnosticError(typeof detail === 'string' ? detail : 'Could not load the assessment. Please try again.', response.status)
  }
  return response.json()
}
export const diagnosticApi = {
  start: (student: number, signal?: AbortSignal) => request<DiagnosticProgress>(student, '/start', signal, {}),
  progress: (student: number, session: string, signal?: AbortSignal) => request<DiagnosticProgress>(student, `/${encodeURIComponent(session)}`, signal),
  answer: (student: number, session: string, body: DiagnosticAnswer, signal?: AbortSignal) => request<DiagnosticFeedback>(student, `/${encodeURIComponent(session)}/answers`, signal, body),
  results: (student: number, session: string, signal?: AbortSignal) => request<DiagnosticResults>(student, `/${encodeURIComponent(session)}/results`, signal),
  complete: (student: number, session: string, signal?: AbortSignal) => request<DiagnosticResults>(student, `/${encodeURIComponent(session)}/complete`, signal, {}),
  restart: (student: number, requestId: string, signal?: AbortSignal) => request<DiagnosticProgress>(student, '/restart', signal, { request_id: requestId }),
}
