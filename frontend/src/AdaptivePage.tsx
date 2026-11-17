import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { Concept } from './api/concepts'
import type { AdaptiveResults } from './api/adaptive'
import { createAdaptiveStore, type AdaptiveState } from './adaptiveStore'
import AttemptFeedback from './AttemptFeedback'
import { RestartConfirmation } from './DiagnosticPage'

export function AdaptiveResultsView({ results, onDashboard, onProgress }: {
  results: AdaptiveResults; onDashboard: () => void; onProgress: () => void
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [results.session_id])
  return <section className="lesson-card" aria-labelledby="adaptive-results">
    <h3 ref={heading} tabIndex={-1} id="adaptive-results">Your adaptive practice results</h3>
    <p role="status">{results.completion_reason === 'eligible_pool_exhausted' ? 'Session complete: no eligible, unused questions remained. Finishing early is expected when the available pool is exhausted.' : 'Session complete: you reached the question target.'}</p>
    <dl className="mt-6 grid gap-4 sm:grid-cols-3">{[
      ['Questions answered', `${results.answered_questions} / ${results.target_questions} target`],
      ['Correct answers', `${results.correct_answers} / ${results.answered_questions}`],
      ['Raw answer accuracy', results.accuracy === null ? 'Not available — no answers recorded' : `${(results.accuracy * 100).toFixed(1)}%`],
    ].map(([label, value]) => <div key={label} className="min-w-0 rounded-xl bg-ice p-4"><dt className="text-sm text-muted">{label}</dt><dd className="mt-2 break-words text-2xl font-semibold">{value}</dd></div>)}</dl>
    <p className="text-sm text-muted">Accuracy counts correct answers in this session. BKT estimated mastery uses recorded learning evidence, including earlier practice. Neither is a trained-model confidence score or measured ability.</p>
    <h4 className="mt-6 font-semibold">BKT estimated mastery by concept</h4>
    {results.concepts.length ? <ul className="mt-4 grid gap-4 sm:grid-cols-2">{results.concepts.map((concept) => <li key={concept.concept_id} className="min-w-0 rounded-xl border border-line bg-snow p-4">
      <p className="break-words font-semibold">{concept.concept_name}</p><p className="mt-2 text-xl">{concept.estimated_mastery === null ? 'Not recorded' : `${(concept.estimated_mastery * 100).toFixed(1)}%`}</p><p className="mt-2 text-sm capitalize text-muted">{concept.status ?? 'Status unavailable'}</p>
    </li>)}</ul> : <p role="status">No concept estimates were recorded for this session.</p>}
    <p className="text-xs text-muted">Estimates are snapshots after each concept’s final adaptive answer. Later learning may change current mastery.</p>
    <h4 className="mt-6 font-semibold">Your session selections</h4>
    {results.questions.length ? <ol className="mt-4 space-y-4">{results.questions.map((item) => <li key={item.position} className="rounded-xl border border-line p-4"><p className="font-semibold">Question {item.position + 1} · {item.is_correct ? 'Correct' : 'Incorrect'}</p><p className="whitespace-pre-wrap break-words text-sm text-muted">{item.selection_reason}</p></li>)}</ol> : <p>No question-selection details were returned.</p>}
    <div className="mt-6 flex flex-wrap gap-3"><button className="button button-primary" onClick={onDashboard}>Dashboard Recommendations</button><button className="button button-secondary" onClick={onProgress}>My Progress</button></div>
  </section>
}

export function AdaptiveQuestion({ state, concepts, onSelect, onSubmit, onContinue, onRefresh }: {
  state: AdaptiveState; concepts: Concept[]; onSelect: (index: number) => void; onSubmit: () => void; onContinue: () => void; onRefresh: () => void
}) {
  const question = state.question
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [question?.id, state.session?.session_id])
  if (!question) return null
  const number = state.feedback ? state.feedback.position + 1 : (state.session?.next_position ?? 0) + 1
  const answered = state.feedback ? number : state.session?.answered_questions ?? 0
  const total = state.totalQuestions ?? 0
  const blocked = !state.feedback && !state.pendingAnswer && state.session?.current_question_eligible !== true
  return <section className="practice-question-card mt-0" aria-busy={state.busy}>
    <div className="flex flex-wrap justify-between gap-3 text-sm text-muted"><p>{concepts.find((concept) => concept.id === question.concept_id)?.name ?? 'Concept name unavailable'}</p><p>Question {number} · target {total}</p></div>
    <label className="mt-4 block text-sm text-muted" htmlFor="adaptive-progress">{answered} of {total} target questions answered</label>
    <progress id="adaptive-progress" className="diagnostic-progress mt-2" value={answered} max={total || 1}>{answered} / {total}</progress>
    <aside className="mt-5 rounded-xl border border-line bg-lavender p-4" aria-labelledby="adaptive-selection"><h4 id="adaptive-selection" className="font-semibold">Why this question was selected</h4><p className="mt-2 whitespace-pre-wrap break-words text-sm">{state.selectionReason || 'No selection reason was returned. Check the current session for details.'}</p></aside>
    {blocked && <div role="status" className="mt-4 rounded-xl bg-blush p-4"><p>{state.session?.blocked_reason || 'Practice eligibility is unavailable. Check the session before answering.'}</p><button className="button button-secondary mt-3" disabled={state.busy} onClick={onRefresh}>Check Current Session</button></div>}
    <h3 ref={heading} tabIndex={-1} id="adaptive-question" className="mt-6 break-words text-xl font-semibold">{question.title}</h3><p className="mt-4 whitespace-pre-wrap break-words text-muted">{question.description}</p>
    <div role="group" aria-labelledby="adaptive-question" className="mt-6 space-y-3">{question.options.map((option, index) => <button key={index} className="practice-option" onClick={() => onSelect(index)} aria-pressed={state.selected === index} disabled={state.busy || state.feedback !== null || state.pendingAnswer || blocked}><span className="practice-option-letter" aria-hidden="true">{String.fromCharCode(65 + index)}</span><span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{option}</span>{state.selected === index && <span className="practice-option-selected">Selected</span>}</button>)}</div>
    {!state.feedback && <button className="button button-primary mt-6 w-full" disabled={state.busy || state.selected === null || blocked} onClick={onSubmit}>{state.busy ? 'Saving Answer...' : state.pendingAnswer ? 'Retry Same Answer' : 'Submit Answer'}</button>}
    <AttemptFeedback question={question} result={state.feedback?.feedback ?? null} hasNext nextLabel="Continue" nextDisabled={state.busy} onNext={onContinue} />
  </section>
}

export default function AdaptivePage({ concepts, onDashboard, onProgress }: { concepts: Concept[]; onDashboard: () => void; onProgress: () => void }) {
  const [store] = useState(() => createAdaptiveStore(1))
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
  const [confirmRestart, setConfirmRestart] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const restart = useRef<HTMLButtonElement>(null)
  useEffect(() => { heading.current?.focus(); return () => store.cancel() }, [store])
  useEffect(() => { if (!confirmRestart) restart.current?.focus() }, [confirmRestart])
  const started = state.session !== null || state.feedback !== null
  const abandoned = state.session?.status === 'abandoned' && !state.feedback
  return <div className="mx-auto max-w-4xl text-ink">
    <header className="lesson-header mb-6"><p className="dashboard-eyebrow">PRACTICE THAT FOLLOWS YOUR LEARNING</p><h2 ref={heading} tabIndex={-1} className="mt-3">Adaptive Practice</h2><p className="mt-3 text-muted">One eligible question at a time.</p></header>
    {state.storageWarning && <p role="status" className="mb-5 text-sm text-feedback-warning">Browser storage is unavailable or was invalid. Retry information is kept for this visit; after a reload, use Start or Resume to recover backend progress.</p>}
    {!started && !state.results && <section className="lesson-card"><h3>A focused learning session</h3><p>Approximately five questions are selected progressively using current BKT estimated mastery, prerequisite eligibility, and previous attempts. Estimates update after each submitted answer.</p><p>This is not a graded examination or a trained AI model. Sessions may finish early when no eligible, unused questions remain. Your existing mastery and learning history are preserved.</p><button className="button button-primary mt-6" disabled={state.busy} onClick={() => { void store.open() }}>Start or Resume Adaptive Practice</button></section>}
    {state.busy && <p role="status" className="my-5 text-sm text-muted">Loading or saving your practice session...</p>}
    {state.error && <div role="alert" className="lesson-card my-5"><p className="text-feedback-error">{state.error}</p><p className="text-sm text-muted">A lost network response does not mean the answer was not saved. Retry to recover the same result.</p><div className="mt-4 flex flex-wrap gap-3"><button className="button button-primary" disabled={state.busy} onClick={() => { void store.retry() }}>Try Again</button>{state.canReconcile && <button className="button button-secondary" disabled={state.busy} onClick={() => { void store.reconcile() }}>Check Current Session</button>}</div></div>}
    {abandoned && <section className="lesson-card"><p role="status">This session was abandoned, possibly after a restart elsewhere.</p><button className="button button-primary mt-4" disabled={state.busy} onClick={() => { void store.reconcile() }}>Check Current Session</button></section>}
    {!abandoned && !state.results && <AdaptiveQuestion state={state} concepts={concepts} onSelect={store.select} onSubmit={() => { void store.submit() }} onContinue={() => { void store.next() }} onRefresh={() => { void store.reconcile() }} />}
    {state.session?.status === 'in_progress' && !state.question && !state.feedback && !state.busy && !state.error && <section className="lesson-card"><p role="status">No current question was returned. Check the session or explicitly restart.</p><button className="button button-secondary mt-4" onClick={() => { void store.reconcile() }}>Check Current Session</button></section>}
    {state.results && <AdaptiveResultsView results={state.results} onDashboard={onDashboard} onProgress={onProgress} />}
    {!confirmRestart && started && <button ref={restart} className="button button-secondary mt-6" disabled={state.busy} onClick={() => setConfirmRestart(true)}>{state.results ? 'Start a New Session' : 'Restart Adaptive Session'}</button>}
    {confirmRestart && <RestartConfirmation busy={state.busy} title="Start a new adaptive session?" message="Any active adaptive session will be abandoned. Your mastery and saved attempts will remain. The backend will select a fresh session of up to five questions." onCancel={() => setConfirmRestart(false)} onConfirm={() => { setConfirmRestart(false); void store.restart() }} />}
  </div>
}
