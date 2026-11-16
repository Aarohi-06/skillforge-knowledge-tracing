import { useEffect, useState } from 'react'
import { fetchProgress, type ConceptProgress, type ProgressResponse } from './api/progress'
import { fetchConceptGraph, type ConceptGraph } from './api/conceptGraph'
import type { Concept } from './api/concepts'
import SkillTree from './SkillTree'
import LearningHistory from './LearningHistory'
import { masteryDisplay } from './masteryDisplay'

const statusStyles = {
  weak: 'bg-blush text-ink',
  learning: 'bg-lavender text-ink',
  mastered: 'bg-ice text-feedback-success',
}

export function ConceptProgressCard({ concept }: { concept: ConceptProgress }) {
  const display = masteryDisplay(concept)

  return (
    <article className="progress-concept-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 break-words text-xl font-semibold tracking-tight text-ink">{concept.concept_name}</h3>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${concept.attempted ? statusStyles[concept.status] : 'bg-snow text-muted'}`}>
          {display.status}
        </span>
      </div>
      <p className={`mt-6 font-semibold tracking-tight ${concept.attempted ? 'text-3xl text-ink' : 'text-xl text-muted'}`}>
        {display.mastery}
        {concept.attempted && <span className="mt-1 block text-sm font-normal tracking-normal text-muted">estimated mastery</span>}
      </p>
      {concept.attempted && (
        <div role="meter" aria-label={`${concept.concept_name} estimated mastery`}
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number((concept.mastery_probability * 100).toFixed(1))}
          aria-valuetext={`${display.mastery} estimated mastery`}
          className="progress-mastery-track">
          <div className="progress-mastery-fill" style={{ width: `${concept.mastery_probability * 100}%` }} />
        </div>
      )}
      <p className="mt-4 text-sm leading-relaxed text-muted">
        {concept.attempted ? 'Updated from your submitted answers.' : 'Start practicing to measure your mastery.'}
      </p>
    </article>
  )
}

export default function ProgressPage({ attemptId, onPractice, onLearn, isSubmitting }: {
  attemptId?: number
  onPractice: (concept: Concept) => void
  onLearn: (concept: Concept) => void
  isSubmitting: boolean
}) {
  const [progress, setProgress] = useState<ProgressResponse | null>(null)
  const [graph, setGraph] = useState<ConceptGraph | null>(null)
  const [graphError, setGraphError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadProgress() {
      setLoading(true)
      setError(null)
      setGraphError(null)
      try {
        const [data, graphResult] = await Promise.all([
          fetchProgress(1, controller.signal),
          fetchConceptGraph(controller.signal).then(
            (value) => ({ value, error: null }),
            () => ({ value: null, error: 'Could not load the skill tree. Please try again.' }),
          ),
        ])
        if (!controller.signal.aborted) setProgress(data)
        if (!controller.signal.aborted) {
          setGraph(graphResult.value)
          setGraphError(graphResult.error)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setError(error instanceof Error ? error.message : 'Could not load progress. Check your connection and try again.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    void loadProgress()
    return () => controller.abort()
  }, [attemptId, retry])

  return (
    <div className="progress-page mx-auto max-w-6xl">
      <header className="progress-header">
        <h2>My Progress</h2>
        <p className="mt-3 max-w-lg text-muted">Your DSA mastery, one concept at a time.</p>
        <p className="mt-2 text-sm text-muted">Showing progress for demo student 1.</p>
      </header>

      {loading && <p role="status" className="progress-state">Loading progress...</p>}

      {!loading && error && (
        <div role="alert" className="progress-state">
          <p className="text-feedback-error">{error}</p>
          <button
            onClick={() => setRetry((value) => value + 1)}
            className="button button-primary mt-5"
          >
            Try Again
          </button>
        </div>
      )}

      {!loading && !error && progress && (
        <>
          <dl className="mt-8 grid gap-4 lg:grid-cols-3">
            {[
              { label: 'Total Concepts', value: progress.summary.total_concepts, surface: 'bg-paper' },
              { label: 'Attempted Concepts', value: progress.summary.attempted_concepts, surface: 'bg-lavender' },
              { label: 'Mastered Concepts', value: progress.summary.mastered_concepts, surface: 'bg-ice' },
            ].map((stat) => (
              <div key={stat.label} className={`progress-summary-card ${stat.surface}`}>
                <dt className="text-sm text-muted">{stat.label}</dt>
                <dd className="mt-3 text-3xl font-semibold tracking-tight text-ink">{stat.value}</dd>
              </div>
            ))}
          </dl>

          <LearningHistory studentId={progress.student_id} concepts={progress.concepts} refreshKey={attemptId} />

          {graphError && (
            <div role="alert" className="progress-state">
              <p className="text-feedback-error">{graphError}</p>
              <button onClick={() => setRetry((value) => value + 1)} className="button button-primary mt-5">Retry Skill Tree</button>
            </div>
          )}
          {graph && !graphError && <SkillTree graph={graph} concepts={progress.concepts} onPractice={onPractice} onLearn={onLearn} isSubmitting={isSubmitting} />}

          {progress.concepts.length === 0 ? (
            <p role="status" className="progress-state">
              No concepts are available yet. Your mastery will appear here once concepts are added.
            </p>
          ) : (
            <div className="mt-8 grid gap-5 lg:grid-cols-2">
              {progress.concepts.map((concept) => (
                <ConceptProgressCard key={concept.concept_id} concept={concept} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
