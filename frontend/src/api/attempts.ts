export interface AttemptCreate {
  student_id: number
  question_id: number
  // Zero-based index into the question's options.
  selected_answer: number
  submission_id?: string
}

export interface AttemptResponse extends Omit<AttemptCreate, 'submission_id'> {
  attempt_id: number
  is_correct: boolean
  correct_answer: number
  mastery_probability: number
  explanation: string | null
}

export type PendingAttempt = AttemptCreate & { submission_id: string }

export function prepareAttemptSubmission(
  previous: PendingAttempt | null,
  attempt: Omit<AttemptCreate, 'submission_id'>,
): PendingAttempt {
  if (previous && previous.student_id === attempt.student_id
    && previous.question_id === attempt.question_id
    && previous.selected_answer === attempt.selected_answer) return previous
  return { ...attempt, submission_id: crypto.randomUUID() }
}

export async function submitAttempt(attempt: AttemptCreate): Promise<AttemptResponse> {
  const response = await fetch('http://127.0.0.1:8000/attempts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(attempt),
  })

  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null)
    const detail = error && typeof error === 'object' && 'detail' in error
      ? error.detail
      : null
    throw new Error(typeof detail === 'string' ? detail : 'Could not submit your answer.')
  }

  return response.json()
}
