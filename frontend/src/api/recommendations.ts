export interface Recommendation {
  concept_id: number
  concept_name: string
  mastery_probability: number
  status: 'weak' | 'learning' | 'mastered'
  action: 'learn' | 'practice' | 'revise'
  reason: string
}

export interface RecommendationsResponse {
  student_id: number
  total_recommendations: number
  recommendations: Recommendation[]
}

export async function fetchRecommendations(
  studentId: number,
  signal?: AbortSignal,
): Promise<RecommendationsResponse> {
  const response = await fetch(`http://127.0.0.1:8000/recommendations/${studentId}`, {
    signal,
    cache: 'no-store',
  })

  if (response.status === 404) {
    throw new Error(`Demo student ${studentId} was not found. Recommendations will be available once this student exists.`)
  }
  if (!response.ok) {
    throw new Error('Could not load recommendations. Please try again.')
  }

  return response.json()
}
