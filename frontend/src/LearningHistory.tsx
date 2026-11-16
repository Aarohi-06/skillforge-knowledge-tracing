import { useEffect, useId, useState, useSyncExternalStore } from 'react'
import type { ConceptProgress } from './api/progress'
import { createHistoryStore, type HistoryState } from './historyStore'
import { HistoryChart, HistoryTable } from './HistoryVisualization'

export function HistoryResults({ state, conceptName, onLoadMore, onRetry }: {
  state: HistoryState
  conceptName: string
  onLoadMore: () => void
  onRetry: () => void
}) {
  return (
    <div aria-busy={state.loading}>
      {state.loading && <p role="status" className="mt-6 text-sm text-muted">{state.attempts.length ? 'Loading more attempts...' : 'Loading learning history...'}</p>}
      {state.error && <div role="alert" className="mt-6 rounded-xl border border-line bg-blush p-5"><p className="text-sm text-feedback-error">{state.error}</p><button className="button button-primary mt-4" onClick={onRetry} disabled={state.loading}>Try Again</button></div>}
      {!state.loading && !state.error && state.attempts.length === 0 && <p role="status" className="mt-6 rounded-xl bg-snow p-5 text-sm text-muted">No recorded attempts for this concept yet. Practice to begin your learning history.</p>}
      {state.attempts.length > 0 && <><HistoryChart attempts={state.attempts} conceptName={conceptName} /><HistoryTable attempts={state.attempts} conceptName={conceptName} /><p role="status" className="mt-3 text-xs text-muted">{state.attempts.length} recorded attempts loaded.</p></>}
      {state.nextCursor !== null && <button className="button button-secondary mt-5" onClick={onLoadMore} disabled={state.loading || state.error !== null}>Load More</button>}
    </div>
  )
}

function ConceptHistory({ studentId, concept }: { studentId: number; concept: ConceptProgress }) {
  const [store] = useState(() => createHistoryStore(studentId, concept.concept_id))
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
  useEffect(() => {
    void store.loadInitial()
    return () => store.cancel()
  }, [store])
  return <HistoryResults state={state} conceptName={concept.concept_name} onLoadMore={() => { void store.loadMore() }} onRetry={() => { void store.retry() }} />
}

export default function LearningHistory({ studentId, concepts, refreshKey }: {
  studentId: number
  concepts: ConceptProgress[]
  refreshKey?: number
}) {
  const id = useId()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = concepts.find((concept) => concept.concept_id === selectedId) ?? concepts[0]
  return (
    <section className="learning-history" aria-labelledby={`${id}-heading`}>
      <h3 id={`${id}-heading`} className="font-editorial text-2xl font-medium tracking-tight sm:text-3xl">Learning History</h3>
      <p className="mt-3 max-w-2xl text-sm text-muted">Explore your recorded practice and BKT estimated mastery over time. These fixed-parameter estimates are not measured ability or test accuracy.</p>
      {selected ? <>
        <label htmlFor={`${id}-concept`} className="mt-6 block text-sm font-medium">Choose a concept</label>
        <select id={`${id}-concept`} className="history-select mt-2" value={selected.concept_id} onChange={(event) => setSelectedId(Number(event.target.value))}>
          {concepts.map((concept) => <option key={concept.concept_id} value={concept.concept_id}>{concept.concept_name}</option>)}
        </select>
        <ConceptHistory key={`${studentId}:${selected.concept_id}:${refreshKey ?? 'initial'}`} studentId={studentId} concept={selected} />
      </> : <p role="status" className="mt-6 text-sm text-muted">No concepts are available to select yet.</p>}
    </section>
  )
}
