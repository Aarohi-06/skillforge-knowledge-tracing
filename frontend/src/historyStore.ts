import { fetchHistory, type HistoryAttempt } from './api/history.ts'

export interface HistoryState {
  attempts: HistoryAttempt[]
  nextCursor: string | null
  loading: boolean
  error: string | null
}

// One store per student/concept. Cancellation also invalidates responses from
// fetch implementations that resolve after abort. Supports StrictMode remounts.
export function createHistoryStore(studentId: number, conceptId: number, fetcher = fetchHistory) {
  let state: HistoryState = { attempts: [], nextCursor: null, loading: true, error: null }
  const listeners = new Set<() => void>()
  let controller: AbortController | null = null
  let generation = 0
  let inFlight = false
  let retryAppend = false

  const update = (next: HistoryState) => {
    state = next
    listeners.forEach((listener) => listener())
  }
  const load = async (append = false) => {
    if (inFlight || (append && state.nextCursor === null)) return
    const cursor = append ? state.nextCursor : null
    controller = new AbortController()
    const signal = controller.signal
    const request = ++generation
    inFlight = true
    retryAppend = append
    update({ attempts: append ? state.attempts : [], nextCursor: append ? state.nextCursor : null, loading: true, error: null })
    try {
      const page = await fetcher(studentId, conceptId, cursor, signal)
      if (signal.aborted || request !== generation) return
      if (page.student_id !== studentId || page.concept_id !== conceptId) {
        throw new Error('History response did not match the selected concept. Please try again.')
      }
      const seen = new Set(state.attempts.map((attempt) => attempt.attempt_id))
      // Preserve backend chronological ordering; deduplicate overlapping pages.
      update({
        attempts: [...state.attempts, ...page.attempts.filter((attempt) => {
          if (seen.has(attempt.attempt_id)) return false
          seen.add(attempt.attempt_id)
          return true
        })],
        nextCursor: page.next_cursor, loading: false, error: null,
      })
    } catch (error) {
      if (signal.aborted || request !== generation) return
      update({ ...state, loading: false, error: error instanceof Error ? error.message : 'Could not load learning history. Please try again.' })
    } finally {
      if (request === generation) inFlight = false
    }
  }
  return {
    getSnapshot: () => state,
    subscribe: (listener: () => void) => {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    loadInitial: () => load(),
    loadMore: () => load(true),
    retry: () => load(retryAppend),
    cancel: () => {
      generation++
      controller?.abort()
      inFlight = false
    },
  }
}
