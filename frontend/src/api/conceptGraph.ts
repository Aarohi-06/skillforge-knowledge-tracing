export interface ConceptGraph {
  nodes: { id: number; name: string }[]
  // Direction is prerequisite -> dependent.
  edges: { source: number; target: number }[]
}

export async function fetchConceptGraph(signal?: AbortSignal): Promise<ConceptGraph> {
  const response = await fetch('http://127.0.0.1:8000/concept-graph', {
    signal,
    cache: 'no-store',
  })
  if (!response.ok) throw new Error('Could not load the skill tree. Please try again.')
  return response.json()
}
