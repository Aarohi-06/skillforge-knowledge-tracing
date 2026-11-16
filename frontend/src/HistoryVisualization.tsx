import { useId } from 'react'
import type { HistoryAttempt } from './api/history'
import { historyPercentage, masterySegments } from './historyChart'

export function HistoryChart({ attempts, conceptName }: { attempts: HistoryAttempt[]; conceptName: string }) {
  const id = useId()
  const segments = masterySegments(attempts)
  if (segments.length === 0) {
    return <p className="mt-6 rounded-xl bg-snow p-5 text-sm text-muted">No recorded mastery points in the loaded history. Legacy attempts are listed below without estimated values.</p>
  }
  return (
    <figure className="mt-6">
      <figcaption className="text-sm font-medium">BKT estimated mastery after recorded attempts</figcaption>
      <div className="history-scroll mt-3 rounded-xl border border-line bg-snow" tabIndex={0} role="region" aria-label="Scrollable mastery chart">
        <svg viewBox="0 0 640 240" className="history-chart" role="img" aria-labelledby={`${id}-title ${id}-description`}>
          <title id={`${id}-title`}>{`${conceptName}: BKT estimated mastery`}</title>
          <desc id={`${id}-description`}>Attempts in chronological order, oldest first. Only recorded after-attempt estimates are plotted. Missing values break the line. Read the chronological table below for dates and values.</desc>
          {[0, 25, 50, 75, 100].map((percent) => {
            const y = 192 - percent * 1.68
            return <g key={percent}><line x1="56" x2="616" y1={y} y2={y} stroke="var(--color-line)" /><text x="46" y={y + 4} textAnchor="end" fill="var(--color-muted)" fontSize="12">{percent}%</text></g>
          })}
          {segments.map((segment) => (
            <g key={segment[0].attemptId}>
              {segment.length > 1 && <polyline data-mastery-segment="true" points={segment.map((point) => `${point.x},${point.y}`).join(' ')} fill="none" stroke="var(--color-primary)" strokeWidth="2.5" />}
              {segment.map((point) => <circle key={point.attemptId} data-attempt-id={point.attemptId} cx={point.x} cy={point.y} r="4" fill="var(--color-primary)" stroke="var(--color-paper)" strokeWidth="1.5"><title>{`Attempt #${point.attemptId}: ${historyPercentage(point.probability)} estimated mastery`}</title></circle>)}
            </g>
          ))}
          <text x={attempts.length === 1 ? 336 : 56} y="212" textAnchor="middle" fill="var(--color-muted)" fontSize="12">1</text>
          {attempts.length > 1 && <text x="616" y="212" textAnchor="middle" fill="var(--color-muted)" fontSize="12">{attempts.length}</text>}
          <text x="336" y="234" textAnchor="middle" fill="var(--color-muted)" fontSize="12">Attempt order (oldest first)</text>
        </svg>
      </div>
      <p className="mt-2 text-xs text-muted">Gaps mean mastery was not recorded. Equal horizontal spacing represents attempt order, not elapsed time. Only loaded attempts are shown.</p>
    </figure>
  )
}

export function HistoryTable({ attempts, conceptName }: { attempts: HistoryAttempt[]; conceptName: string }) {
  return (
    <div className="history-scroll mt-6 rounded-xl border border-line" tabIndex={0} role="region" aria-label="Scrollable chronological attempt history">
      <table className="history-table">
        <caption>{conceptName} attempt history · oldest first · times shown in your local timezone</caption>
        <thead><tr><th scope="col">Attempt</th><th scope="col">Date / time</th><th scope="col">Result</th><th scope="col">Estimated mastery before</th><th scope="col">Estimated mastery after</th><th scope="col">Snapshots</th></tr></thead>
        <tbody>{attempts.map((attempt) => (
          <tr key={attempt.attempt_id}>
            <th scope="row">#{attempt.attempt_id}</th>
            <td><time dateTime={attempt.attempted_at}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(attempt.attempted_at))}</time></td>
            <td><span className={`rounded-full px-3 py-1 text-xs font-medium ${attempt.is_correct ? 'bg-ice text-feedback-success' : 'bg-blush text-feedback-error'}`}>{attempt.is_correct ? 'Correct' : 'Incorrect'}</span></td>
            <td>{historyPercentage(attempt.mastery_before)}</td>
            <td>{historyPercentage(attempt.mastery_after)}</td>
            <td className="text-muted">{attempt.snapshots_available ? 'Recorded' : attempt.mastery_before === null && attempt.mastery_after === null ? 'Historical snapshots unavailable' : 'Partial snapshots'}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}
