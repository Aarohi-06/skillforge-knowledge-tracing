import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { fetchResources } from '../src/api/resources.ts'
import { createLessonStore } from '../src/lessonStore.ts'
import { unmetPrerequisites } from '../src/practiceAccess.ts'

const catalog = JSON.parse(await readFile(new URL('../../data/concept_resources.json', import.meta.url), 'utf8'))
const lesson = { ...catalog.lessons[0], concept_id: 72, schema_version: 1, content_version: '1.0.0' }
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }

test('resources API sends the actual concept ID and cancellation signal without student data or writes', async (t) => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/concepts/72/resources')
    assert.equal(options.signal, controller.signal)
    assert.equal(options.cache, 'no-store')
    assert.equal(options.method, undefined)
    assert.equal(options.body, undefined)
    return Response.json(lesson)
  })
  assert.deepEqual(await fetchResources(72, controller.signal), lesson)
})

test('all eight actual lesson structures pass through without content changes', async (t) => {
  for (const [index, content] of catalog.lessons.entries()) {
    const actual = { ...content, concept_id: index + 90, schema_version: 1, content_version: catalog.content_version }
    t.mock.method(globalThis, 'fetch', async () => Response.json(actual))
    assert.deepEqual(await fetchResources(index + 90), actual)
  }
})

for (const detail of ['Concept not found', 'Learning resources not found for this concept', 'Learning resource content is invalid or unavailable']) {
  test(`lesson API preserves backend error: ${detail}`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail }, { status: 404 }))
    await assert.rejects(fetchResources(72), { message: detail })
  })
}

test('lesson API handles non-JSON errors, empty responses, and wrong concept/schema', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('Unavailable', { status: 500 }))
  await assert.rejects(fetchResources(72), /Could not load/)
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }))
  assert.equal(await fetchResources(72), null)
  for (const body of [{ ...lesson, concept_id: 8 }, { ...lesson, schema_version: 2 }]) {
    t.mock.method(globalThis, 'fetch', async () => Response.json(body))
    await assert.rejects(fetchResources(72), /did not match/)
  }
})

test('lesson loading, error, retry and empty state transitions notify subscribers', async () => {
  let calls = 0
  const store = createLessonStore(72, async () => { if (++calls === 1) throw new Error('Offline'); return calls === 2 ? lesson : null })
  const states = []
  const unsubscribe = store.subscribe(() => states.push(store.getSnapshot()))
  assert.equal(store.getSnapshot().loading, true)
  await store.load()
  assert.equal(store.getSnapshot().error, 'Offline')
  await store.load()
  assert.equal(store.getSnapshot().lesson, lesson)
  assert.equal(store.getSnapshot().error, null)
  await store.load()
  assert.deepEqual(store.getSnapshot(), { lesson: null, loading: false, error: null })
  assert.ok(states.some((state) => state.loading))
  unsubscribe()
})

test('rapid concept switching aborts and discards a late lesson even when fetch ignores abort', async () => {
  const delayed = deferred()
  let signal
  const old = createLessonStore(72, async (_id, value) => { signal = value; return delayed.promise })
  const pending = old.load()
  old.cancel()
  const current = createLessonStore(73, async () => ({ ...lesson, concept_id: 73, concept_name: 'Recursion' }))
  await current.load()
  delayed.resolve(lesson)
  await pending
  assert.equal(signal.aborted, true)
  assert.equal(old.getSnapshot().lesson, null)
  assert.equal(current.getSnapshot().lesson.concept_name, 'Recursion')
})

test('effect replay and late errors cannot overwrite a newer lesson response', async () => {
  const delayed = deferred()
  let calls = 0
  const store = createLessonStore(72, () => ++calls === 1 ? delayed.promise : Promise.resolve(lesson))
  const pending = store.load()
  store.cancel()
  await store.load()
  delayed.reject(new Error('Old failure'))
  await pending
  assert.equal(store.getSnapshot().lesson, lesson)
  assert.equal(store.getSnapshot().error, null)
})

test('eligibility follows only incoming immediate prerequisite mastered statuses', () => {
  const graph = { nodes: [], edges: [{ source: 4, target: 7 }, { source: 5, target: 7 }, { source: 7, target: 8 }] }
  assert.deepEqual(unmetPrerequisites(7, graph, [{ concept_id: 4, status: 'mastered' }, { concept_id: 5, status: 'learning' }]), [5])
  assert.deepEqual(unmetPrerequisites(7, graph, [{ concept_id: 4, status: 'mastered' }, { concept_id: 5, status: 'mastered' }]), [])
  assert.deepEqual(unmetPrerequisites(7, graph, []), [4, 5])
  assert.deepEqual(unmetPrerequisites(4, graph, []), [])
})
