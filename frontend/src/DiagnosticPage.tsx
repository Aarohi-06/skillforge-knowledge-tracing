import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { Concept } from './api/concepts'
import type { DiagnosticResults } from './api/diagnostics'
import { createDiagnosticStore, type DiagnosticState } from './diagnosticStore'
import AttemptFeedback from './AttemptFeedback'

export function DiagnosticResultsView({ results, onDashboard, onProgress }: {
  results: DiagnosticResults; onDashboard: () => void; onProgress: () => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [results.session_id])
  return <section className="lesson-card" aria-labelledby="diagnostic-results">
    <h3 ref={heading} tabIndex={-1} id="diagnostic-results" className="font-editorial text-2xl">Your diagnostic results</h3>
    <dl className="mt-6 grid gap-4 sm:grid-cols-3">
      {[
        ['Questions completed', `${results.answered_questions} / ${results.total_questions}`],
        ['Correct answers', `${results.correct_answers} / ${results.total_questions}`],
        ['Raw diagnostic accuracy', `${(results.accuracy * 100).toFixed(1)}%`],
      ].map(([label, value]) => <div key={label} className="rounded-xl bg-ice p-4"><dt className="text-sm text-muted">{label}</dt><dd className="mt-2 text-2xl font-semibold">{value}</dd></div>)}
    </dl>
    <p className="mt-5 text-sm text-muted">Accuracy counts answers correct in this assessment. BKT estimated mastery reflects your recorded learning evidence, including earlier practice. These estimates are not measured ability or a trained-model confidence score.</p>
    <h4 className="mt-6 font-semibold">BKT estimated mastery by concept</h4>
    {results.concepts.length ? <ul className="mt-4 grid gap-4 sm:grid-cols-3">{results.concepts.map((concept) => <li className="min-w-0 rounded-xl border border-line bg-snow p-4" key={concept.concept_id}>
      <p className="break-words font-semibold">{concept.concept_name}</p>
      <p className="mt-2 text-xl">{concept.estimated_mastery === null ? 'Not recorded' : `${(concept.estimated_mastery * 100).toFixed(1)}%`}</p>
      <p className="mt-2 text-sm capitalize text-muted">{concept.status ?? 'Status unavailable'}</p>
    </li>)}</ul> : <p role="status" className="mt-4 text-muted">No per-concept estimates were returned.</p>}
    <p className="mt-4 text-xs text-muted">Estimates recorded after each concept’s final diagnostic answer. Later practice may change your current mastery.</p>
    <div className="mt-6 flex flex-wrap gap-3"><button onClick={onDashboard} className="button button-primary">Dashboard Recommendations</button><button onClick={onProgress} className="button button-secondary">My Progress</button></div>
  </section>
}

export function DiagnosticQuestion({ state, concepts, onSelect, onSubmit, onNext }: {
  state: DiagnosticState; concepts: Concept[]; onSelect: (index: number) => void; onSubmit: () => void; onNext: () => void
}) {
  const question = state.question
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [question?.id])
  if (!question) return null
  const number = state.feedback ? state.feedback.position + 1 : (state.session?.next_position ?? 0) + 1
  const completed = state.feedback ? number : state.session?.answered_questions ?? 0
  const total = state.totalQuestions ?? 0
  const concept = concepts.find((item) => item.id === question.concept_id)
  return <section className="practice-question-card mt-0" aria-busy={state.busy}>
    <div className="flex flex-wrap justify-between gap-3 text-sm text-muted"><p>{concept?.name ?? 'Concept name unavailable'}</p><p>Question {number}{total > 0 ? ` of ${total}` : ''}</p></div>
    <label className="mt-4 block text-sm text-muted" htmlFor="diagnostic-progress">{completed} of {total} questions answered</label>
    <progress id="diagnostic-progress" className="diagnostic-progress mt-2" value={completed} max={total || 1}>{completed} of {total}</progress>
    <h3 ref={heading} tabIndex={-1} id="diagnostic-question" className="mt-6 break-words text-xl font-semibold">{question.title}</h3>
    <p className="mt-4 whitespace-pre-wrap break-words text-muted">{question.description}</p>
    <div role="group" aria-labelledby="diagnostic-question" className="mt-6 space-y-3">{question.options.map((option, index) => <button key={index} className="practice-option" aria-pressed={state.selected === index}
      disabled={state.busy || state.feedback !== null || state.pendingAnswer} onClick={() => onSelect(index)}>
      <span className="practice-option-letter" aria-hidden="true">{String.fromCharCode(65 + index)}</span><span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{option}</span>{state.selected === index && <span className="practice-option-selected">Selected</span>}
    </button>)}</div>
    {!state.feedback && <button className="button button-primary mt-6 w-full" onClick={onSubmit} disabled={state.busy || state.selected === null}>{state.busy ? 'Saving Answer...' : state.pendingAnswer ? 'Retry Same Answer' : 'Submit Answer'}</button>}
    <AttemptFeedback question={question} result={state.feedback?.feedback ?? null} hasNext onNext={onNext} nextDisabled={state.busy} nextLabel={number === total ? 'View Results' : 'Next Question'} />
  </section>
}

export function RestartConfirmation({ onConfirm, onCancel, busy, title = 'Restart this diagnostic?', message = 'The current active assessment will be abandoned. Your mastery and all saved attempts will remain. A new six-question assessment will begin.' }: { onConfirm: () => void; onCancel: () => void; busy: boolean; title?: string; message?: string }) {
  const cancel = useRef<HTMLButtonElement>(null)
  useEffect(() => { cancel.current?.focus() }, [])
  return <section aria-labelledby="restart-heading" className="lesson-card mt-6 border-mist bg-blush">
    <h3 id="restart-heading">{title}</h3>
    <p>{message}</p>
    <div className="mt-5 flex flex-wrap gap-3"><button ref={cancel} className="button button-secondary" disabled={busy} onClick={onCancel}>Keep Current Assessment</button><button className="button button-primary" disabled={busy} onClick={onConfirm}>Confirm Restart</button></div>
  </section>
}

export default function DiagnosticPage({ concepts, onDashboard, onProgress }: { concepts: Concept[]; onDashboard: () => void; onProgress: () => void }) {
  const [store] = useState(() => createDiagnosticStore(1))
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
  const [confirmRestart, setConfirmRestart] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const restartButton = useRef<HTMLButtonElement>(null)
  useEffect(() => { heading.current?.focus(); return () => store.cancel() }, [store])
  useEffect(() => { if (!confirmRestart) restartButton.current?.focus() }, [confirmRestart])
  const started = state.session !== null || state.feedback !== null
  const closed = state.session?.status === 'abandoned' && !state.feedback
  return <div className="mx-auto max-w-4xl text-ink">
    <header className="lesson-header mb-6"><p className="dashboard-eyebrow">A PLACE TO BEGIN</p><h2 ref={heading} tabIndex={-1} className="mt-3">Diagnostic Assessment</h2><p className="mt-3 text-muted">Find a starting point for your learning.</p></header>
    {state.storageWarning && <p role="status" className="mb-5 text-sm text-feedback-warning">Browser storage is unavailable or was invalid. Retry information is kept for this visit; after a reload, use Start or Resume to recover backend progress.</p>}
    {!started && !state.results && <section className="lesson-card"><h3>Discover your foundations</h3><p>Six questions cover Arrays, Time Complexity, and Recursion. Your answers help estimate current mastery and personalize learning. This is not a graded exam.</p><p>Your existing mastery is not reset. Each saved answer updates your BKT estimate, and restarting keeps your learning history.</p><button className="button button-primary mt-6" disabled={state.busy} onClick={() => { void store.open() }}>Start or Resume Assessment</button></section>}
    {state.busy && <p role="status" className="my-5 text-sm text-muted">Loading or saving your assessment...</p>}
    {state.error && <div role="alert" className="lesson-card my-5"><p className="text-feedback-error">{state.error}</p><p className="mt-2 text-sm text-muted">A network error does not mean your answer was lost. Retry to recover the same saved result.</p><div className="mt-4 flex flex-wrap gap-3"><button className="button button-primary" disabled={state.busy} onClick={() => { void store.retry() }}>Try Again</button>{state.canReconcile && <button className="button button-secondary" disabled={state.busy} onClick={() => { void store.reconcile() }}>Check Current Assessment</button>}</div></div>}
    {closed && <section className="lesson-card"><p role="status">This assessment was abandoned, possibly after a restart elsewhere.</p><button disabled={state.busy} className="button button-primary mt-4" onClick={() => { void store.reconcile() }}>Check Current Assessment</button></section>}
    {!closed && !state.results && <DiagnosticQuestion state={state} concepts={concepts} onSelect={store.select} onSubmit={() => { void store.submit() }} onNext={() => { void store.next() }} />}
    {state.session?.status === 'in_progress' && !state.question && !state.feedback && !state.busy && !state.error && <p role="status" className="lesson-card">No next question was returned. Check the current assessment or restart.<button className="button button-secondary mt-4" onClick={() => { void store.reconcile() }}>Check Current Assessment</button></p>}
    {state.results && <DiagnosticResultsView results={state.results} onDashboard={onDashboard} onProgress={onProgress} />}
    {!confirmRestart && started && <button ref={restartButton} disabled={state.busy} className="button button-secondary mt-6" onClick={() => setConfirmRestart(true)}>Restart Assessment</button>}
    {confirmRestart && <RestartConfirmation busy={state.busy} onCancel={() => setConfirmRestart(false)} onConfirm={() => { setConfirmRestart(false); void store.restart() }} />}
  </div>
}
