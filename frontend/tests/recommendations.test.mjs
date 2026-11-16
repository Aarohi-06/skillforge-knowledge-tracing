import assert from 'node:assert/strict'
import { test } from 'node:test'
import { fetchRecommendations } from '../src/api/recommendations.ts'

test('recommendations preserve backend explanations and ordering for every action', async (t) => {
  const recommendations = [
    {
      concept_id: 1, concept_name: 'Arrays', mastery_probability: 0.2,
      status: 'weak', action: 'revise',
      reason: 'Your mastery of Arrays is low. Revise this concept.',
    },
    {
      concept_id: 2, concept_name: 'Stacks', mastery_probability: 0.6,
      status: 'learning', action: 'practice',
      reason: 'You are making progress in Stacks. Continue practicing to strengthen your understanding.',
    },
    {
      concept_id: 3, concept_name: 'Recursion', mastery_probability: 0.2,
      status: 'weak', action: 'learn', reason: 'Recursion is ready to learn.',
    },
  ]
  const payload = { student_id: 1, total_recommendations: 3, recommendations }
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.equal(url, 'http://127.0.0.1:8000/recommendations/1')
    return new Response(JSON.stringify(payload), {
      headers: { 'Content-Type': 'application/json' },
    })
  })

  const result = await fetchRecommendations(1)

  assert.deepEqual(result, payload)
  assert.deepEqual(result.recommendations.map((item) => item.reason), recommendations.map((item) => item.reason))
})
