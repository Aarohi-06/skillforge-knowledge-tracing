import assert from 'node:assert/strict'
import { test } from 'node:test'
import { prepareAttemptSubmission, submitAttempt } from '../src/api/attempts.ts'

const answer = { student_id: 1, question_id: 8, selected_answer: 0 }

test('same intended answer keeps its UUID; different answers/questions/students receive new UUIDs', () => {
  const pending = prepareAttemptSubmission(null, answer)
  assert.match(pending.submission_id, /^[0-9a-f-]{36}$/)
  assert.equal(prepareAttemptSubmission(pending, { ...answer }), pending)
  for (const change of [{ selected_answer: 1 }, { question_id: 9 }, { student_id: 2 }]) {
    assert.notEqual(prepareAttemptSubmission(pending, { ...answer, ...change }).submission_id, pending.submission_id)
  }
})

test('a genuinely new attempt after reset receives a fresh UUID, even for the same answer', () => {
  assert.notEqual(prepareAttemptSubmission(null, answer).submission_id, prepareAttemptSubmission(null, answer).submission_id)
})

test('a lost response can be retried with the same UUID and payload', async (t) => {
  const sent = []
  const feedback = { ...answer, attempt_id: 10, is_correct: true, correct_answer: 0, mastery_probability: 0.57647, explanation: 'The recorded authored explanation.' }
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    sent.push(JSON.parse(options.body))
    if (sent.length === 1) throw new TypeError('Response lost')
    return Response.json(feedback)
  })
  let pending = prepareAttemptSubmission(null, answer)
  await assert.rejects(submitAttempt(pending), /Response lost/)
  pending = prepareAttemptSubmission(pending, answer)
  assert.deepEqual(await submitAttempt(pending), feedback)
  assert.deepEqual(sent[0], sent[1])
  assert.equal(sent.length, 2)
})
