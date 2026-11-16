import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let RecommendationCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } } })
  RecommendationCard = (await server.ssrLoadModule('/src/RecommendationsSection.tsx')).RecommendationCard
})
after(async () => { await server?.close() })

for (const [action, reason] of [
  ['learn', 'Arrays is ready to learn.'],
  ['practice', 'You are making progress in Arrays. Continue practicing to strengthen your understanding.'],
  ['revise', 'Your mastery of Arrays is low. Revise this concept.'],
]) {
  test(`${action} card renders the actual reason directly after the name, without a static label`, () => {
    const recommendation = {
      concept_id: 1, concept_name: 'Arrays', action, reason,
      mastery_probability: 0.2, status: 'weak',
    }
    const html = renderToStaticMarkup(createElement(RecommendationCard, {
      recommendation, isSubmitting: false, onPractice: () => {},
    }))
    assert.match(html, new RegExp(`</h4><p[^>]*>${reason.replaceAll('.', '\\.')}</p><button`))
    assert.ok(!html.includes('Why recommended'))
    assert.ok(html.includes('whitespace-normal break-words'))
    assert.ok(!/line-clamp|truncate|overflow-hidden/.test(html))
    assert.ok(html.includes(action === 'learn' ? 'Start Learning' : '>Practice</button>'))
  })
}

test('pending submissions still disable the practice button', () => {
  const html = renderToStaticMarkup(createElement(RecommendationCard, {
    recommendation: { concept_id: 1, concept_name: 'Arrays', action: 'learn', reason: 'Arrays is ready to learn.', mastery_probability: 0.2, status: 'weak' },
    isSubmitting: true, onPractice: () => {},
  }))
  assert.match(html, /<button disabled=""/)
})
