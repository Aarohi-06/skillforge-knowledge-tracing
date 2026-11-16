export interface ConceptResources {
  concept_id: number
  concept_name: string
  schema_version: 1
  content_version: string
  overview: { explanation: string; why_it_matters: string }
  key_ideas: { term: string; explanation: string }[]
  worked_example: { title: string; steps: string[]; language: 'python'; code: string; expected_output: string }
  common_mistakes: { mistake: string; explanation: string }[]
  complexity: {
    assumptions: string[]
    notes: string
    operations: { operation: string; time: string; auxiliary_space: string }[]
  }
  resources: {
    title: string; url: string
    resource_type: 'documentation' | 'interactive_textbook' | 'article' | 'video'
    verification_status: 'verified' | 'unverified'
    verified_on: string | null
  }[]
}

export async function fetchResources(conceptId: number, signal?: AbortSignal): Promise<ConceptResources | null> {
  const response = await fetch(`http://127.0.0.1:8000/concepts/${conceptId}/resources`, { signal, cache: 'no-store' })
  if (response.status === 204) return null
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : 'Could not load this lesson. Please try again.')
  }
  const lesson: ConceptResources | null = await response.json()
  if (lesson && (lesson.concept_id !== conceptId || lesson.schema_version !== 1)) {
    throw new Error('The lesson did not match the selected concept or supported content format.')
  }
  return lesson
}
