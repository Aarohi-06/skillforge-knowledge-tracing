import assert from 'node:assert/strict'
import { test } from 'node:test'
import { masteryDisplay, skillTreeDisplay } from '../src/masteryDisplay.ts'

const initial = {
  concept_id: 1, concept_name: 'Arrays', mastery_probability: 0.2,
  status: 'weak', attempted: false,
}

test('unattempted concepts hide the initial probability in both views', () => {
  assert.deepEqual(masteryDisplay(initial), { status: 'Not Started', mastery: 'Not Started' })
  assert.equal(skillTreeDisplay(initial, true), 'Locked · Not Started')
  assert.equal(skillTreeDisplay(initial, false), 'Ready to Learn')
  assert.equal(initial.mastery_probability, 0.2)
})

test('attempted concepts retain actual estimated mastery, even at the initial probability', () => {
  for (const [status, probability, label] of [
    ['weak', 0.2, 'Weak'], ['learning', 0.6123, 'Learning'], ['mastered', 0.9, 'Mastered'],
  ]) {
    const concept = { ...initial, attempted: true, status, mastery_probability: probability }
    const percentage = `${(probability * 100).toFixed(1)}%`
    assert.deepEqual(masteryDisplay(concept), { status: label, mastery: percentage })
    for (const locked of [true, false]) {
      assert.equal(skillTreeDisplay(concept, locked), `${label} · ${percentage} estimated mastery`)
    }
  }
})

test('missing progress is displayed as unavailable', () => {
  assert.equal(masteryDisplay(undefined).mastery, 'Mastery unavailable')
  assert.equal(skillTreeDisplay(undefined, false), 'Mastery unavailable')
})
