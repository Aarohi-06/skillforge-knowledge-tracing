import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, HistoryChart, HistoryTable, HistoryResults, LearningHistory
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } } })
  ;({ HistoryChart, HistoryTable } = await server.ssrLoadModule('/src/HistoryVisualization.tsx'))
  ;({ HistoryResults, default: LearningHistory } = await server.ssrLoadModule('/src/LearningHistory.tsx'))
})
after(async () => { await server?.close() })
const row = (id, value = 0.6) => ({ attempt_id: id, question_id: 1, concept_id: 2,
  attempted_at: '2026-01-01T10:00:00Z', is_correct: id % 2 === 1,
  mastery_before: value === null ? null : 0.2, mastery_after: value,
  origin: 'ordinary_practice', snapshots_available: value !== null })
const render = (component, props) => renderToStaticMarkup(createElement(component, props))

test('single point has accessible SVG title and a dot without an invented line', () => {
  const html = render(HistoryChart, { attempts: [row(1)], conceptName: 'Arrays' })
  assert.ok(html.includes('role="img"'))
  assert.ok(html.includes('aria-labelledby='))
  assert.ok(html.includes('Arrays: BKT estimated mastery'))
  assert.equal((html.match(/<circle /g) ?? []).length, 1)
  assert.ok(!html.includes('<polyline'))
  assert.ok(html.includes('60.0% estimated mastery'))
})

test('missing snapshot splits chart lines and legacy-only history has no plotted values', () => {
  const html = render(HistoryChart, { attempts: [row(1), row(2), row(3, null), row(4), row(5)], conceptName: 'Arrays' })
  assert.equal((html.match(/data-mastery-segment=/g) ?? []).length, 2)
  assert.equal((html.match(/<circle /g) ?? []).length, 4)
  const legacy = render(HistoryChart, { attempts: [row(1, null)], conceptName: 'Arrays' })
  assert.ok(legacy.includes('No recorded mastery points'))
  assert.ok(!legacy.includes('<svg'))
})

test('table preserves chronology, correct/incorrect text, timestamps and unavailable values', () => {
  const html = render(HistoryTable, { attempts: [row(7, null), row(2, 0.6123)], conceptName: 'Arrays' })
  assert.ok(html.includes('<caption>Arrays attempt history'))
  assert.ok(html.includes('oldest first'))
  assert.ok(html.includes('scope="col"'))
  assert.ok(html.includes('scope="row"'))
  assert.ok(html.indexOf('#7') < html.indexOf('#2'))
  assert.ok(html.includes('dateTime="2026-01-01T10:00:00Z"'))
  assert.ok(html.includes('Correct'))
  assert.ok(html.includes('Incorrect'))
  assert.ok(html.includes('61.2%'))
  assert.equal((html.match(/Not recorded/g) ?? []).length, 2)
  assert.ok(html.includes('Historical snapshots unavailable'))
})

test('loading, empty, failure/retry, and Load More controls render readable states', () => {
  const props = { state: { attempts: [], nextCursor: null, loading: true, error: null }, conceptName: 'Arrays', onLoadMore() {}, onRetry() {} }
  const loading = render(HistoryResults, props)
  assert.ok(loading.includes('Loading learning history...'))
  assert.ok(loading.includes('aria-busy="true"'))
  const empty = render(HistoryResults, { ...props, state: { ...props.state, loading: false } })
  assert.ok(empty.includes('No recorded attempts'))
  const error = render(HistoryResults, { ...props, state: { ...props.state, loading: false, error: 'Student not found' } })
  assert.ok(error.includes('role="alert"'))
  assert.ok(error.includes('Student not found'))
  assert.ok(error.includes('Try Again'))
  const more = render(HistoryResults, { ...props, state: { attempts: [row(1)], nextCursor: 'next', loading: false, error: null } })
  assert.ok(more.includes('Load More'))
  const pending = render(HistoryResults, { ...props, state: { attempts: [row(1)], nextCursor: 'next', loading: true, error: null } })
  assert.ok(pending.includes('Loading more attempts...'))
  assert.match(pending, /<button[^>]*disabled=""[^>]*>Load More/)
})

test('concept selector is labeled, defaults to existing concepts, and empty concepts are handled', () => {
  const concept = { concept_id: 2, concept_name: 'Arrays', attempted: false, status: 'weak', mastery_probability: 0.2 }
  const html = render(LearningHistory, { studentId: 1, concepts: [concept] })
  assert.ok(html.includes('Choose a concept'))
  assert.ok(html.includes('<label for='))
  assert.ok(html.includes('<select id='))
  assert.ok(html.includes('value="2" selected=""'))
  assert.ok(html.includes('not measured ability or test accuracy'))
  const empty = render(LearningHistory, { studentId: 1, concepts: [] })
  assert.ok(empty.includes('No concepts are available'))
  assert.ok(!empty.includes('<select'))
})
