import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, AttemptFeedback
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } } })
  AttemptFeedback = (await server.ssrLoadModule('/src/AttemptFeedback.tsx')).default
})
after(async () => { await server?.close() })

const question = { id: 81, concept_id: 12, title: 'Array access', description: 'Access by index?', difficulty: 'easy', options: ['O(n)', 'O(log n)', 'O(1)', 'O(n²)'] }
const feedback = { attempt_id: 11, student_id: 1, question_id: 81, selected_answer: 2, is_correct: true,
  correct_answer: 2, explanation: 'Index access computes the location directly, so it takes O(1) time.', mastery_probability: 0.57647 }
const props = { question, result: feedback, hasNext: true, onNext() {} }
const render = (changes = {}) => renderToStaticMarkup(createElement(AttemptFeedback, { ...props, ...changes }))

for (const correct of [true, false]) {
  test(`${correct ? 'correct' : 'incorrect'} submission shows the authorized correct option, explanation and unchanged mastery formatting`, () => {
    const html = render({ result: { ...feedback, is_correct: correct, selected_answer: correct ? 2 : 0 } })
    assert.ok(html.includes(correct ? '>Correct!</h4>' : '>Incorrect.</h4>'))
    assert.ok(html.includes('>Correct answer</h5>'))
    assert.ok(html.includes('C. O(1)'))
    assert.ok(html.includes(feedback.explanation))
    assert.ok(html.includes('>Explanation</h5>'))
    assert.ok(html.includes('Updated BKT mastery: 57.6%'))
    assert.ok(html.indexOf('Correct answer') < html.indexOf('Explanation'))
    assert.ok(html.indexOf('Explanation') < html.indexOf('Updated BKT mastery'))
  })
}

for (const explanation of [null, '', '   ']) {
  test(`missing explanation (${JSON.stringify(explanation)}) uses the concise fallback`, () => {
    const html = render({ result: { ...feedback, explanation } })
    assert.ok(html.includes('An explanation is not available for this question yet.'))
    assert.ok(html.includes('C. O(1)'))
    assert.ok(html.includes('Updated BKT mastery: 57.6%'))
  })
}

test('before submission, during a pending request, or after an unsuccessful request there is no answer/explanation markup', () => {
  // The App sets attemptResult only after a successful, matching response.
  const html = render({ result: null })
  assert.equal(html, '')
})

test('rapid question/concept changes hide old feedback, and a new success renders only the new explanation', () => {
  for (const next of [
    { ...question, id: 82 },
    { ...question, id: 90, concept_id: 55 },
    { ...question, id: 91, concept_id: 66 },
  ]) {
    assert.equal(render({ question: next }), '')
    assert.equal(render({ question: next, result: null }), '')
  }
  const html = render({ question: { ...question, id: 90, concept_id: 55 }, result: { ...feedback, question_id: 90, explanation: 'A different recorded explanation.' } })
  assert.ok(html.includes('A different recorded explanation.'))
  assert.ok(!html.includes(feedback.explanation))
})

test('explanation and answer markup are escaped as text, with readable wrapping', () => {
  const explanation = '<img src=x onerror="alert(1)">\n<script>alert(2)</script>'
  const html = render({ question: { ...question, options: ['a', 'b', '<strong>O(1)</strong>'] }, result: { ...feedback, explanation } })
  assert.ok(!html.includes('<img'))
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('<strong>'))
  assert.ok(html.includes('&lt;img'))
  assert.ok(html.includes('&lt;strong&gt;O(1)&lt;/strong&gt;'))
  assert.ok(html.includes('whitespace-pre-wrap break-words'))
})

test('feedback announces politely and atomically; Next Question remains a native keyboard-operable button', () => {
  const html = render()
  assert.ok(html.includes('role="status" aria-live="polite" aria-atomic="true"'))
  assert.ok(html.includes('aria-hidden="true"'))
  assert.match(html, /<button[^>]*class="button button-primary mt-5">Next Question<\/button>/)
  let next = 0
  const element = AttemptFeedback({ ...props, onNext: () => next++ })
  element.props.children[1].props.onClick()
  assert.equal(next, 1)
})

test('last question keeps completion feedback, and zero mastery is formatted correctly', () => {
  const html = render({ hasNext: false, result: { ...feedback, mastery_probability: 0 } })
  assert.ok(html.includes('You have completed all questions for this concept.'))
  assert.ok(!html.includes('Next Question'))
  assert.ok(html.includes('Updated BKT mastery: 0.0%'))
})

test('an invalid authorized answer index is not guessed from the selected answer', () => {
  const html = render({ result: { ...feedback, correct_answer: 99 } })
  assert.ok(html.includes('Correct answer unavailable.'))
  assert.ok(!html.includes('C. O(1)'))
  assert.ok(html.includes(feedback.explanation))
})
