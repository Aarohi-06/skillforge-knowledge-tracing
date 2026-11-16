import assert from 'node:assert/strict'
import { test } from 'node:test'
import { submitAttempt } from '../src/api/attempts.ts'
import { fetchConcepts } from '../src/api/concepts.ts'
import { fetchQuestions } from '../src/api/questions.ts'
import { fetchProgress } from '../src/api/progress.ts'
import { fetchRecommendations } from '../src/api/recommendations.ts'
import { fetchConceptGraph } from '../src/api/conceptGraph.ts'

test('submitting an answer sends exactly one JSON POST with a zero-based index', async (t) => {
  const request = { student_id: 1, question_id: 8, selected_answer: 0 }
  const feedback = { ...request, attempt_id: 5, is_correct: true, correct_answer: 0, mastery_probability: 0.57647 }
  const fetch = t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/attempts')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), request)
    return Response.json(feedback)
  })
  assert.deepEqual(await submitAttempt(request), feedback)
  assert.equal(fetch.mock.callCount(), 1)
})

test('attempt errors retain backend detail and do not retry automatically', async (t) => {
  const request = { student_id: 1, question_id: 8, selected_answer: 1 }
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Student not found' }, { status: 404 }))
  await assert.rejects(submitAttempt(request), /Student not found/)
  assert.equal(fetch.mock.callCount(), 1)
  assert.equal(request.selected_answer, 1)
})

test('attempts handle non-JSON server failures', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('Server error', { status: 500 }))
  await assert.rejects(submitAttempt({ student_id: 1, question_id: 1, selected_answer: 0 }), /Could not submit/)
})

const readers = [
  { path: '/concepts', read: fetchConcepts, data: [] },
  { path: '/questions', read: fetchQuestions, data: [] },
  { path: '/progress/1', read: fetchProgress, data: { student_id: 1, summary: { total_concepts: 0, attempted_concepts: 0, mastered_concepts: 0 }, concepts: [] } },
  { path: '/recommendations/1', read: fetchRecommendations, data: { student_id: 1, total_recommendations: 0, recommendations: [] } },
  { path: '/concept-graph', read: () => fetchConceptGraph(), data: { nodes: [], edges: [] } },
]
for (const { path, read, data } of readers) {
  test(`${path} uses the local backend URL and preserves empty results`, async (t) => {
    t.mock.method(globalThis, 'fetch', async (url) => {
      assert.equal(url, `http://127.0.0.1:8000${path}`)
      return Response.json(data)
    })
    assert.deepEqual(await read(1), data)
  })
  test(`${path} rejects API failures and can be retried`, async (t) => {
    let calls = 0
    t.mock.method(globalThis, 'fetch', async () => ++calls === 1
      ? new Response('Error', { status: 500 }) : Response.json(data))
    await assert.rejects(read(1))
    assert.deepEqual(await read(1), data)
  })
}

for (const read of [fetchProgress, fetchRecommendations]) {
  test(`${read.name} explains a missing demo student`, async (t) => {
    t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Student not found' }, { status: 404 }))
    await assert.rejects(read(1), /Demo student 1 was not found/)
  })
  test(`${read.name} forwards cancellation and avoids stale HTTP cache`, async (t) => {
    const controller = new AbortController()
    t.mock.method(globalThis, 'fetch', async (_url, options) => {
      assert.equal(options.signal, controller.signal)
      assert.equal(options.cache, 'no-store')
      throw new DOMException('Cancelled', 'AbortError')
    })
    await assert.rejects(read(1, controller.signal), { name: 'AbortError' })
  })
}
