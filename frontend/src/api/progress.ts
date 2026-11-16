export interface ConceptProgress {
  concept_id: number
  concept_name: string
  mastery_probability: number
  status: 'weak' | 'learning' | 'mastered'
  attempted: boolean
}

export interface ProgressResponse {
  student_id: number
  summary: {
    total_concepts: number
    attempted_concepts: number
    mastered_concepts: number
  }
  concepts: ConceptProgress[]
}

export async function fetchProgress(
  studentId: number,
  signal?: AbortSignal,
): Promise<ProgressResponse> {
  const response = await fetch(`http://127.0.0.1:8000/progress/${studentId}`, {
    signal,
    cache: 'no-store',
  })

  if (response.status === 404) {
    throw new Error(`Demo student ${studentId} was not found. Progress will be available once this student exists.`)
  }
  if (!response.ok) {
    throw new Error('Could not load progress. Please try again.')
  }

  return response.json()
}
