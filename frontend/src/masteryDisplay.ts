import type { ConceptProgress } from './api/progress'

export function masteryDisplay(concept: ConceptProgress | undefined) {
  if (!concept) return { status: 'Unavailable', mastery: 'Mastery unavailable' }
  if (!concept.attempted) return { status: 'Not Started', mastery: 'Not Started' }
  return {
    status: { weak: 'Weak', learning: 'Learning', mastered: 'Mastered' }[concept.status],
    mastery: `${(concept.mastery_probability * 100).toFixed(1)}%`,
  }
}

export function skillTreeDisplay(concept: ConceptProgress | undefined, locked: boolean) {
  if (!concept) return 'Mastery unavailable'
  if (!concept.attempted) return locked ? 'Locked · Not Started' : 'Ready to Learn'
  const display = masteryDisplay(concept)
  return `${display.status} · ${display.mastery} estimated mastery`
}
