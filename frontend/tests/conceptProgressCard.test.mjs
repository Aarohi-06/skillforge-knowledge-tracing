import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server
let ConceptProgressCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } } })
  ConceptProgressCard = (await server.ssrLoadModule('/src/ProgressPage.tsx')).ConceptProgressCard
})
after(async () => { await server?.close() })

const concept = { concept_id: 1, concept_name: 'Arrays', attempted: false, status: 'weak', mastery_probability: 0.2 }
const render = (item) => renderToStaticMarkup(createElement(ConceptProgressCard, { concept: item }))

test('unattempted concept shows Not Started without a percentage or mastery meter', () => {
  const html = render(concept)
  assert.ok(html.includes('Not Started'))
  assert.ok(!html.includes('20.0%'))
  assert.ok(!html.includes('role="meter"'))
})

for (const [status, probability, label] of [
  ['weak', 0.2, 'Weak'], ['learning', 0.6123, 'Learning'], ['mastered', 0.9, 'Mastered'],
]) {
  test(`attempted ${status} concept renders actual mastery and an accessible meter`, () => {
    const html = render({ ...concept, attempted: true, status, mastery_probability: probability })
    assert.ok(html.includes(label))
    assert.ok(html.includes(`${(probability * 100).toFixed(1)}%`))
    assert.ok(html.includes('role="meter"'))
    assert.ok(html.includes('aria-label="Arrays estimated mastery"'))
    assert.ok(html.includes(`aria-valuenow="${Number((probability * 100).toFixed(1))}"`))
    assert.ok(html.includes(`width:${probability * 100}%`))
  })
}
