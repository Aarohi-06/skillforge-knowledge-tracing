import { useEffect, useState } from 'react'
import { fetchRecommendations, type Recommendation } from './api/recommendations'

const actionStyles = {
  learn: { label: 'Learn', badge: 'bg-lavender text-ink' },
  practice: { label: 'Practice', badge: 'bg-ice text-ink' },
  revise: { label: 'Revise', badge: 'bg-blush text-ink' },
}

interface Props {
  attemptId?: number
  isSubmitting: boolean
  onPractice: (recommendation: Recommendation) => void
  onLearn: (recommendation: Recommendation) => void
}

export function RecommendationCard({ recommendation, isSubmitting, onPractice, onLearn }: {
  recommendation: Recommendation
  isSubmitting: boolean
  onPractice: Props['onPractice']
  onLearn: Props['onLearn']
}) {
  return (
    <article className="recommendation-card">
      <span className={`self-start rounded-full px-3 py-1 text-xs font-semibold tracking-wide ${actionStyles[recommendation.action].badge}`}>
        {actionStyles[recommendation.action].label}
      </span>
      <h4 className="mt-5 break-words text-xl font-semibold tracking-tight text-ink">{recommendation.concept_name}</h4>
      <p className="mt-3 mb-8 whitespace-normal break-words text-sm leading-relaxed text-muted">
        {recommendation.reason}
      </p>
      <button
        onClick={() => recommendation.action === 'practice' ? onPractice(recommendation) : onLearn(recommendation)}
        disabled={isSubmitting}
        aria-label={`${recommendation.action === 'learn' ? 'Start learning' : recommendation.action === 'revise' ? 'Review lesson for' : 'Practice'} ${recommendation.concept_name}`}
        className="button button-primary mt-auto self-start"
      >
        {recommendation.action === 'learn' ? 'Start Learning' : recommendation.action === 'revise' ? 'Review Lesson' : 'Practice'}
      </button>
      {recommendation.action === 'revise' && <button className="button button-secondary mt-3 self-start" disabled={isSubmitting}
        aria-label={`Practice ${recommendation.concept_name}`} onClick={() => onPractice(recommendation)}>Practice</button>}
    </article>
  )
}

export default function RecommendationsSection({ attemptId, isSubmitting, onPractice, onLearn }: Props) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadRecommendations() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchRecommendations(1, controller.signal)
        if (!controller.signal.aborted) setRecommendations(data.recommendations)
      } catch (error) {
        if (!controller.signal.aborted) {
          setError(error instanceof Error ? error.message : 'Could not load recommendations. Check your connection and try again.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    void loadRecommendations()
    return () => controller.abort()
  }, [attemptId, retry])

  return (
    <section aria-labelledby="recommendations-heading" className="mt-8 sm:mt-10">
      <h3 id="recommendations-heading" className="font-editorial text-2xl font-medium tracking-tight text-ink sm:text-3xl">Recommended Next Steps</h3>
      <p className="mt-3 text-sm text-muted">Personalized suggestions for demo student 1.</p>

      {loading && <p role="status" className="recommendations-state">Loading recommendations...</p>}

      {!loading && error && (
        <div role="alert" className="recommendations-state">
          <p className="text-feedback-error">{error}</p>
          <button
            onClick={() => setRetry((value) => value + 1)}
            className="button button-primary mt-5"
          >
            Try Again
          </button>
        </div>
      )}

      {!loading && !error && (recommendations.length === 0 ? (
        <p role="status" className="recommendations-state">
          No recommendations are available right now. You can still explore concepts on the Practice page.
        </p>
      ) : (
        <div className="mt-6 grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {recommendations.map((recommendation) => (
            <RecommendationCard key={recommendation.concept_id} recommendation={recommendation} isSubmitting={isSubmitting} onPractice={onPractice} onLearn={onLearn} />
          ))}
        </div>
      ))}
      {isSubmitting && <p role="status" className="mt-4 text-sm text-muted">Saving your answer. Recommended practice will be available shortly.</p>}
    </section>
  )
}
