import { fetchResources, type ConceptResources } from './api/resources.ts'

export interface LessonState {
  lesson: ConceptResources | null
  loading: boolean
  error: string | null
}

// Each selected concept owns its request lifecycle, including StrictMode replays.
export function createLessonStore(conceptId: number, fetcher = fetchResources) {
  let state: LessonState = { lesson: null, loading: true, error: null }
  let controller: AbortController | null = null
  const listeners = new Set<() => void>()
  const update = (next: LessonState) => { state = next; listeners.forEach((notify) => notify()) }
  return {
    getSnapshot: () => state,
    subscribe: (notify: () => void) => { listeners.add(notify); return () => { listeners.delete(notify) } },
    cancel: () => { controller?.abort() },
    async load() {
      controller?.abort()
      const request = new AbortController()
      controller = request
      update({ lesson: null, loading: true, error: null })
      try {
        const lesson = await fetcher(conceptId, request.signal)
        if (!request.signal.aborted) update({ lesson, loading: false, error: null })
      } catch (error) {
        if (!request.signal.aborted) update({ lesson: null, loading: false,
          error: error instanceof Error ? error.message : 'Could not load this lesson. Please try again.' })
      }
    },
  }
}
