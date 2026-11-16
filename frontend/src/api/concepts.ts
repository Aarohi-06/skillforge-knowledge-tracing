
export interface Concept {
  id: number
  name: string
  description: string | null
}

export async function fetchConcepts(): Promise<Concept[]> {
  const response = await fetch('http://127.0.0.1:8000/concepts')

  if (!response.ok) {
    throw new Error('Failed to fetch concepts')
  }

  return response.json()
}
