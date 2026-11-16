import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { Concept } from './api/concepts'
import type { ConceptResources } from './api/resources'
import { fetchConceptGraph, type ConceptGraph } from './api/conceptGraph'
import { fetchProgress, type ProgressResponse } from './api/progress'
import { createLessonStore, type LessonState } from './lessonStore'
import { unmetPrerequisites } from './practiceAccess'

export function LessonContent({ lesson }: { lesson: ConceptResources }) {
  return <div className="lesson-sections">
    <section className="lesson-card" aria-labelledby="lesson-overview">
      <h3 id="lesson-overview">Overview</h3>
      <p>{lesson.overview.explanation}</p>
      <h4>Why it matters</h4><p>{lesson.overview.why_it_matters}</p>
    </section>
    <section className="lesson-card" aria-labelledby="lesson-ideas">
      <h3 id="lesson-ideas">Key ideas</h3>
      <dl className="space-y-5 mt-5">{lesson.key_ideas.map((idea) => <div key={idea.term}><dt className="font-semibold">{idea.term}</dt><dd className="mt-2 text-muted">{idea.explanation}</dd></div>)}</dl>
    </section>
    <section className="lesson-card" aria-labelledby="lesson-example">
      <h3 id="lesson-example">Worked example</h3><h4>{lesson.worked_example.title}</h4>
      <ol className="mt-4 list-decimal space-y-3 pl-6 text-muted">{lesson.worked_example.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
      <p className="text-xs font-semibold">Python</p>
      <pre tabIndex={0} aria-label="Worked example Python code"><code>{lesson.worked_example.code}</code></pre>
      <h4>Expected output</h4><pre tabIndex={0} aria-label="Expected output"><samp>{lesson.worked_example.expected_output}</samp></pre>
    </section>
    <section className="lesson-card" aria-labelledby="lesson-mistakes">
      <h3 id="lesson-mistakes">Common mistakes</h3>
      <ul className="mt-5 space-y-5">{lesson.common_mistakes.map((item) => <li key={item.mistake}><h4 className="!mt-0">{item.mistake}</h4><p>{item.explanation}</p></li>)}</ul>
    </section>
    <section className="lesson-card" aria-labelledby="lesson-complexity">
      <h3 id="lesson-complexity">Complexity</h3><h4>Assumptions</h4>
      <ul className="mt-3 list-disc space-y-2 pl-6 text-muted">{lesson.complexity.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
      <p>{lesson.complexity.notes}</p>
      <div className="mt-5 overflow-x-auto" tabIndex={0} role="region" aria-label="Scrollable complexity table">
        <table className="lesson-table"><caption className="sr-only">Complexity by operation</caption><thead><tr><th scope="col">Operation</th><th scope="col">Time</th><th scope="col">Auxiliary space</th></tr></thead>
          <tbody>{lesson.complexity.operations.map((item) => <tr key={item.operation}><th scope="row">{item.operation}</th><td>{item.time}</td><td>{item.auxiliary_space}</td></tr>)}</tbody></table>
      </div>
    </section>
    <section className="lesson-card" aria-labelledby="lesson-links">
      <h3 id="lesson-links">Keep exploring</h3>
      {lesson.resources.length ? <ul className="mt-5 space-y-5">{lesson.resources.map((link) => {
        // Only navigable web links; never allow script URLs from content.
        let safe = false
        try { safe = ['https:', 'http:'].includes(new URL(link.url).protocol) } catch { /* Show title without a link. */ }
        return <li key={link.url}>{safe ? <a className="font-medium underline underline-offset-4" href={link.url} target="_blank" rel="noopener noreferrer">{link.title}<span className="sr-only"> (opens in a new tab)</span></a> : <span>{link.title} (link unavailable)</span>}
          <span className="mt-1 block text-xs text-muted">{link.resource_type.replaceAll('_', ' ')} · {link.verification_status === 'verified' ? `Link verified ${link.verified_on}` : 'Link unverified'}</span></li>
      })}</ul> : <p>No external resources are listed for this lesson.</p>}
    </section>
  </div>
}

export function LessonResults({ state, onRetry }: { state: LessonState; onRetry: () => void }) {
  if (state.loading) return <p role="status" className="lesson-card">Loading lesson...</p>
  if (state.error) return <div role="alert" className="lesson-card"><p className="text-feedback-error">{state.error}</p><button className="button button-primary mt-4" onClick={onRetry}>Retry Lesson</button></div>
  if (!state.lesson) return <div className="lesson-card"><p role="status">No learning content is available for this concept yet.</p><button className="button button-secondary mt-4" onClick={onRetry}>Retry Lesson</button></div>
  return <LessonContent lesson={state.lesson} />
}

export function LessonPractice({ concept, graph, progress, loading, error, isSubmitting, onRetry, onPractice }: {
  concept: Concept; graph: ConceptGraph | null; progress: ProgressResponse | null
  loading: boolean; error: string | null; isSubmitting: boolean
  onRetry: () => void; onPractice: (concept: Concept) => void
}) {
  const known = graph?.nodes.some((node) => node.id === concept.id) && progress?.concepts.some((item) => item.concept_id === concept.id)
  const blocked = graph && progress ? unmetPrerequisites(concept.id, graph, progress.concepts) : []
  const eligible = !loading && !error && known && blocked.length === 0
  return <section className="lesson-card bg-ice" aria-labelledby="lesson-practice">
    <h3 id="lesson-practice">Put it into practice</h3>
    <p id="lesson-practice-status" role="status">{loading ? 'Checking practice prerequisites...' : error ? error : !known ? 'Practice eligibility is unavailable for this concept.' : blocked.length ? `Practice is locked. Master these immediate prerequisites first: ${blocked.map((id) => graph?.nodes.find((node) => node.id === id)?.name ?? `Concept ${id}`).join(', ')}.` : 'Practice is unlocked. All immediate prerequisites are satisfied.'}{isSubmitting ? ' Please wait while your answer is saved.' : ''}</p>
    <p className="text-sm text-muted">Reading lessons does not change mastery or unlock practice.</p>
    <div className="mt-5 flex flex-wrap gap-3">
      <button className="button button-primary" disabled={!eligible || isSubmitting} aria-describedby="lesson-practice-status" onClick={() => onPractice(concept)}>{blocked.length ? '🔒 Practice Locked' : 'Practice'}</button>
      {!loading && (error || !known) && <button className="button button-secondary" onClick={onRetry}>Retry Practice Eligibility</button>}
    </div>
  </section>
}

export default function ConceptLearning({ concept, concepts, onSelect, onBack, backLabel, onPractice, isSubmitting, attemptId }: {
  concept: Concept; onBack: () => void; backLabel: string; onPractice: (concept: Concept) => void
  concepts: Concept[]; onSelect: (concept: Concept) => void
  isSubmitting: boolean; attemptId?: number
}) {
  const [store] = useState(() => createLessonStore(concept.id))
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
  const heading = useRef<HTMLHeadingElement>(null)
  const [access, setAccess] = useState<{ graph: ConceptGraph | null; progress: ProgressResponse | null; loading: boolean; error: string | null; attemptId?: number }>({ graph: null, progress: null, loading: true, error: null })
  const [retry, setRetry] = useState(0)
  useEffect(() => { heading.current?.focus(); void store.load(); return () => store.cancel() }, [store])
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([fetchConceptGraph(controller.signal), fetchProgress(1, controller.signal)]).then(([graph, progress]) => {
      if (!controller.signal.aborted) setAccess({ graph, progress, loading: false, error: null, attemptId })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setAccess({ graph: null, progress: null, loading: false, error: error instanceof Error ? error.message : 'Could not check practice prerequisites.', attemptId })
    })
    return () => controller.abort()
  }, [retry, attemptId])
  return <div className="concept-learning mx-auto max-w-4xl" aria-busy={state.loading}>
    <button className="button button-secondary mb-6" onClick={onBack}>← Back to {backLabel}</button>
    <header className="lesson-header"><p className="dashboard-eyebrow">CONCEPT LEARNING</p><h2 ref={heading} tabIndex={-1} className="mt-3 break-words">{concept.name}</h2>
      <p className="mt-3 text-muted">{concept.description || 'Explore the foundations, follow a worked example, and review the key ideas at your own pace.'}</p>
      {state.lesson && <p className="mt-3 text-xs text-muted">Content version {state.lesson.content_version}</p>}
    </header>
    {concepts.length > 0 && <div className="my-6"><label htmlFor="lesson-concept" className="block text-sm font-medium">Choose a lesson</label>
      <select id="lesson-concept" className="history-select mt-2" value={concept.id} onChange={(event) => { const next = concepts.find((item) => item.id === Number(event.target.value)); if (next) onSelect(next) }}>
        {!concepts.some((item) => item.id === concept.id) && <option value={concept.id}>{concept.name}</option>}
        {concepts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></div>}
    <LessonResults state={state} onRetry={() => { void store.load() }} />
    <LessonPractice concept={concept} {...access} loading={access.loading || access.attemptId !== attemptId} isSubmitting={isSubmitting} onPractice={onPractice} onRetry={() => { setAccess({ graph: null, progress: null, loading: true, error: null }); setRetry((value) => value + 1) }} />
  </div>
}
