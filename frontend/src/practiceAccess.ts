import type { ConceptGraph } from './api/conceptGraph'
import type { ConceptProgress } from './api/progress'

// Match the backend: every immediate prerequisite must have mastered status.
export function unmetPrerequisites(id: number, graph: ConceptGraph, concepts: ConceptProgress[]) {
  const progress = new Map(concepts.map((concept) => [concept.concept_id, concept]))
  return graph.edges.filter((edge) => edge.target === id)
    .map((edge) => edge.source).filter((source) => progress.get(source)?.status !== 'mastered')
}
