
export interface Question {
  id: number
  concept_id: number
  title: string
  description: string | null
  difficulty: string
  options: string[]
}

export async function fetchQuestions(): Promise<Question[]> {
  const response = await fetch('http://127.0.0.1:8000/questions')

  if (!response.ok) {
    throw new Error('Failed to fetch questions')
  }

  return response.json()
}
