import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fetchHistory } from '../src/api/history.ts'
import { createHistoryStore } from '../src/historyStore.ts'
import { historyPercentage, masterySegments } from '../src/historyChart.ts'

const attempt = (id, after = 0.6) => ({
  attempt_id: id, question_id: 1, concept_id: 2, attempted_at: '2026-01-01T10:00:00Z',
  is_correct: true, mastery_before: after === null ? null : 0.2,
  mastery_after: after, origin: 'ordinary_practice', snapshots_available: after !== null,
})
const page = (attempts = [], next_cursor = null, concept_id = 2) => ({ student_id: 1, concept_id, attempts, next_cursor })
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('history API sends concept filter, page limit, opaque cursor, cache and cancellation options', async (t) => {
  const controller = new AbortController()
  const cursor = 'opaque+/=?'
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const parsed = new URL(url)
    assert.equal(parsed.origin + parsed.pathname, 'http://127.0.0.1:8000/students/1/history')
    assert.equal(parsed.searchParams.get('concept_id'), '2')
    assert.equal(parsed.searchParams.get('limit'), '50')
    assert.equal(parsed.searchParams.get('cursor'), cursor)
    assert.equal(options.signal, controller.signal)
    assert.equal(options.cache, 'no-store')
    return Response.json(page([attempt(1)]))
  })
  assert.deepEqual(await fetchHistory(1, 2, cursor, controller.signal), page([attempt(1)]))
})

test('first history page omits a cursor and preserves null snapshots', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.equal(new URL(url).searchParams.has('cursor'), false)
    return Response.json(page([attempt(1, null)]))
  })
  assert.equal((await fetchHistory(1, 2)).attempts[0].mastery_after, null)
})

for (const detail of ['Student not found', 'Concept not found', 'Invalid history cursor']) {
  test(`history API reports ${detail}`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail }, { status: 404 }))
    await assert.rejects(fetchHistory(1, 2), { message: detail })
  })
}

test('history API handles non-JSON failures', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('Error', { status: 500 }))
  await assert.rejects(fetchHistory(1, 2), /Could not load learning history/)
})

test('empty history transitions from loading to an empty result', async () => {
  const store = createHistoryStore(1, 2, async () => page())
  assert.equal(store.getSnapshot().loading, true)
  await store.loadInitial()
  assert.deepEqual(store.getSnapshot(), { attempts: [], nextCursor: null, loading: false, error: null })
})

test('Load More preserves backend order, follows cursor, deduplicates and prevents duplicate requests', async () => {
  const later = deferred()
  const cursors = []
  const store = createHistoryStore(1, 2, async (_student, _concept, cursor) => {
    cursors.push(cursor)
    return cursor === null ? page([attempt(8), attempt(2)], 'next-page') : later.promise
  })
  await store.loadInitial()
  const loading = store.loadMore()
  const duplicate = store.loadMore()
  assert.equal(store.getSnapshot().loading, true)
  assert.deepEqual(store.getSnapshot().attempts.map((item) => item.attempt_id), [8, 2])
  later.resolve(page([attempt(2), attempt(9)]))
  await Promise.all([loading, duplicate])
  assert.deepEqual(cursors, [null, 'next-page'])
  assert.deepEqual(store.getSnapshot().attempts.map((item) => item.attempt_id), [8, 2, 9])
  await store.loadMore()
  assert.equal(cursors.length, 2)
})

test('failed Load More retains rows and retries the same cursor', async () => {
  const cursors = []
  const store = createHistoryStore(1, 2, async (_student, _concept, cursor) => {
    cursors.push(cursor)
    if (cursors.length === 1) return page([attempt(1)], 'next')
    if (cursors.length === 2) throw new Error('Temporary failure')
    return page([attempt(2)])
  })
  await store.loadInitial()
  await store.loadMore()
  assert.equal(store.getSnapshot().error, 'Temporary failure')
  assert.equal(store.getSnapshot().attempts.length, 1)
  assert.equal(store.getSnapshot().nextCursor, 'next')
  await store.retry()
  assert.deepEqual(cursors, [null, 'next', 'next'])
  assert.deepEqual(store.getSnapshot().attempts.map((item) => item.attempt_id), [1, 2])
  assert.equal(store.getSnapshot().error, null)
})

test('initial error and retry notify subscribers and recover', async () => {
  let calls = 0
  const states = []
  const store = createHistoryStore(1, 2, async () => {
    if (++calls === 1) throw new Error('Unavailable')
    return page([attempt(1)])
  })
  const unsubscribe = store.subscribe(() => states.push(store.getSnapshot()))
  await store.loadInitial()
  assert.equal(store.getSnapshot().error, 'Unavailable')
  await store.retry()
  assert.equal(store.getSnapshot().attempts.length, 1)
  assert.equal(store.getSnapshot().error, null)
  assert.ok(states.some((state) => state.loading))
  unsubscribe()
})

test('concept switch aborts and ignores a late previous response even if fetch ignores abort', async () => {
  const oldResponse = deferred()
  let oldSignal
  const old = createHistoryStore(1, 2, async (_student, _concept, _cursor, signal) => {
    oldSignal = signal
    return oldResponse.promise
  })
  const pending = old.loadInitial()
  old.cancel()
  const selected = createHistoryStore(1, 3, async () => page([{ ...attempt(9), concept_id: 3 }], null, 3))
  await selected.loadInitial()
  oldResponse.resolve(page([attempt(1)]))
  await pending
  assert.equal(oldSignal.aborted, true)
  assert.deepEqual(old.getSnapshot().attempts, [])
  assert.equal(selected.getSnapshot().attempts[0].concept_id, 3)
})

test('cancel/reload is safe during StrictMode effect replay and late failures', async () => {
  const first = deferred()
  let calls = 0
  const store = createHistoryStore(1, 2, () => ++calls === 1 ? first.promise : Promise.resolve(page([attempt(2)])))
  const pending = store.loadInitial()
  store.cancel()
  await store.loadInitial()
  first.reject(new Error('Old request failed'))
  await pending
  assert.equal(store.getSnapshot().error, null)
  assert.equal(store.getSnapshot().attempts[0].attempt_id, 2)
})

test('response with mismatched concept scope becomes a retryable error', async () => {
  const store = createHistoryStore(1, 2, async () => page([attempt(1)], null, 3))
  await store.loadInitial()
  assert.match(store.getSnapshot().error, /did not match/)
  assert.deepEqual(store.getSnapshot().attempts, [])
})

test('single actual zero point is plotted without inventing an initial estimate', () => {
  const segments = masterySegments([attempt(1, 0)])
  assert.equal(segments.length, 1)
  assert.equal(segments[0].length, 1)
  assert.equal(segments[0][0].probability, 0)
  assert.equal(segments[0][0].x, 336)
  assert.equal(historyPercentage(null), 'Not recorded')
  assert.equal(historyPercentage(0), '0.0%')
})

test('chart segments break at missing snapshots and use only actual after values', () => {
  const rows = [attempt(1, 0.2), attempt(2, 0.4), attempt(3, null), attempt(4, 0.6), attempt(5, 0.8)]
  const segments = masterySegments(rows)
  assert.deepEqual(segments.map((segment) => segment.map((point) => point.attemptId)), [[1, 2], [4, 5]])
  assert.deepEqual(segments.flat().map((point) => point.probability), [0.2, 0.4, 0.6, 0.8])
  assert.deepEqual(masterySegments([attempt(1, null)]), [])
  assert.equal(masterySegments([{ ...attempt(1, 0.7), mastery_before: null, snapshots_available: false }])[0][0].probability, 0.7)
})
