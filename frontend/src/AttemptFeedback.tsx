import type { AttemptResponse } from './api/attempts'
import type { Question } from './api/questions'

export default function AttemptFeedback({ question, result, hasNext, onNext, nextLabel = 'Next Question', nextDisabled = false }: {
  question: Question
  result: AttemptResponse | null
  hasNext: boolean
  onNext: () => void
  nextLabel?: string
  nextDisabled?: boolean
}) {
  // A result authorizes feedback for its own question only. New questions must
  // never render a previously recorded explanation or answer index.
  if (!result || result.question_id !== question.id) return null
  const index = result.correct_answer
  const validIndex = Number.isInteger(index) && index >= 0 && index < question.options.length

  return <div className="practice-feedback" data-correct={result.is_correct}>
    <div role="status" aria-live="polite" aria-atomic="true">
      <h4 className="flex items-center gap-2 font-editorial text-2xl font-medium">
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0"><circle cx="12" cy="12" r="9" /><path d={result.is_correct ? 'M8 12l3 3 5-6' : 'M9 9l6 6 M15 9l-6 6'} /></svg>
        {result.is_correct ? 'Correct!' : 'Incorrect.'}
      </h4>
      <div className="mt-5 space-y-5 text-sm leading-relaxed text-ink">
        <div>
          <h5 className="font-semibold">Correct answer</h5>
          <p className="mt-2 whitespace-pre-wrap break-words">{validIndex ? `${String.fromCharCode(65 + index)}. ${question.options[index]}` : 'Correct answer unavailable.'}</p>
        </div>
        <div className="rounded-xl border border-line bg-paper p-4 sm:p-5">
          <h5 className="font-semibold">Explanation</h5>
          <p className="mt-2 whitespace-pre-wrap break-words">{result.explanation?.trim() ? result.explanation : 'An explanation is not available for this question yet.'}</p>
        </div>
        <p>Updated BKT mastery: {(result.mastery_probability * 100).toFixed(1)}%</p>
      </div>
    </div>
    {hasNext ? <button onClick={onNext} disabled={nextDisabled} className="button button-primary mt-5">{nextLabel}</button>
      : <p className="mt-5 text-sm font-medium text-ink">You have completed all questions for this concept.</p>}
  </div>
}
