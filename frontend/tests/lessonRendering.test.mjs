import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, LessonContent, LessonResults, LessonPractice, RecommendationCard, ReadLessonButton
const catalog = JSON.parse(await readFile(new URL('../../data/concept_resources.json', import.meta.url), 'utf8'))
const lesson = { ...catalog.lessons[0], concept_id: 72, schema_version: 1, content_version: '1.0.0' }
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: { port: 0 } } })
  ;({ LessonContent, LessonResults, LessonPractice } = await server.ssrLoadModule('/src/ConceptLearning.tsx'))
  ;({ RecommendationCard } = await server.ssrLoadModule('/src/RecommendationsSection.tsx'))
  ;({ ReadLessonButton } = await server.ssrLoadModule('/src/SkillTree.tsx'))
})
after(async () => { await server?.close() })
const render = (component, props) => renderToStaticMarkup(createElement(component, props))
const buttons = (element) => (Array.isArray(element.props.children) ? element.props.children : [element.props.children]).filter((child) => child?.type === 'button')

test('all eight lessons render structured headings, actual text, steps, code, and complexity', () => {
  for (const content of catalog.lessons) {
    const html = render(LessonContent, { lesson: content })
    for (const title of ['Overview', 'Key ideas', 'Worked example', 'Common mistakes', 'Complexity', 'Assumptions', 'Keep exploring']) assert.ok(html.includes(`>${title}</h3>`) || html.includes(`>${title}</h4>`))
    assert.ok(html.includes('aria-labelledby="lesson-example"'))
    assert.ok(html.includes('<ol '))
    assert.match(html, /<pre tabindex="0" aria-label="Worked example Python code"><code>/i)
    assert.ok(html.includes('scope="col"'))
    assert.ok(html.includes('scope="row"'))
    assert.ok(!html.includes('"schema_version"'))
    assert.ok(!html.includes('dangerouslySetInnerHTML'))
  }
})

test('resource links are safe, typed, and disclose verification and new-tab behavior', () => {
  const html = render(LessonContent, { lesson })
  assert.ok(html.includes('target="_blank" rel="noopener noreferrer"'))
  assert.ok(html.includes('opens in a new tab'))
  assert.ok(html.includes('Link verified 2026-11-16'))
  assert.ok(html.includes('documentation'))
  const malicious = render(LessonContent, { lesson: { ...lesson, resources: [{ ...lesson.resources[0], url: 'javascript:alert(1)', verification_status: 'unverified', verified_on: null }] } })
  assert.ok(!malicious.includes('href='))
  assert.ok(malicious.includes('Link unverified'))
  assert.ok(render(LessonContent, { lesson: { ...lesson, resources: [] } }).includes('No external resources'))
})

test('lesson loading, missing content, API error and retry render semantic states and invoke retry', () => {
  const base = { lesson: null, loading: false, error: null }
  assert.ok(render(LessonResults, { state: { ...base, loading: true } }).includes('role="status"'))
  assert.ok(render(LessonResults, { state: base }).includes('No learning content'))
  assert.ok(render(LessonResults, { state: { ...base, error: 'Concept not found' } }).includes('role="alert"'))
  let count = 0
  const element = LessonResults({ state: { ...base, error: 'Offline' }, onRetry: () => count++ })
  buttons(element)[0].props.onClick()
  assert.equal(count, 1)
})

const concept = { id: 72, name: 'Binary Search', description: null }
const graph = { nodes: [{ id: 4, name: 'Arrays' }, { id: 72, name: 'Binary Search' }], edges: [{ source: 4, target: 72 }] }
const progress = (status) => ({ student_id: 1, concepts: [{ concept_id: 4, status }, { concept_id: 72, status: 'weak' }] })
const access = { concept, graph, progress: progress('mastered'), loading: false, error: null, isSubmitting: false, onPractice() {}, onRetry() {} }

test('locked, unlocked, missing-student, loading, missing data and saving practice states fail closed', () => {
  const locked = render(LessonPractice, { ...access, progress: progress('learning') })
  assert.ok(locked.includes('Master these immediate prerequisites first: Arrays'))
  assert.match(locked, /<button[^>]*disabled=""[^>]*>🔒 Practice Locked/)
  assert.ok(locked.includes('aria-describedby="lesson-practice-status"'))
  assert.ok(!render(LessonPractice, access).includes('disabled=""'))
  for (const extra of [{ loading: true }, { error: 'Student not found' }, { graph: null }, { progress: null }, { isSubmitting: true }]) {
    assert.ok(render(LessonPractice, { ...access, ...extra }).includes('disabled=""'))
  }
  const missing = render(LessonPractice, { ...access, error: 'Student not found' })
  assert.ok(missing.includes('Retry Practice Eligibility'))
  assert.ok(missing.includes('Reading lessons does not change mastery'))
})

test('eligible lesson Practice passes the same selected concept to existing navigation', () => {
  let selected
  const element = LessonPractice({ ...access, onPractice: (value) => { selected = value } })
  const actions = element.props.children.find((child) => child?.type === 'div')
  buttons(actions)[0].props.onClick()
  assert.equal(selected, concept)
})

for (const action of ['learn', 'practice', 'revise']) {
  test(`${action} recommendation navigates to the intended lesson/practice, preserving revision Practice`, () => {
    const recommendation = { concept_id: 72, concept_name: 'Arrays', action, reason: 'Actual backend reason.' }
    const calls = []
    const element = RecommendationCard({ recommendation, isSubmitting: false, onLearn: (value) => calls.push(['learn', value]), onPractice: (value) => calls.push(['practice', value]) })
    const actions = buttons(element)
    actions[0].props.onClick()
    assert.deepEqual(calls[0], [action === 'practice' ? 'practice' : 'learn', recommendation])
    if (action === 'revise') { actions[1].props.onClick(); assert.deepEqual(calls[1], ['practice', recommendation]) }
  })
}

test('Skill Tree Read Lesson remains enabled for any selected concept and passes its identity', () => {
  let selected
  const element = ReadLessonButton({ concept, onLearn: (value) => { selected = value } })
  assert.equal(element.props.disabled, undefined)
  element.props.onClick()
  assert.equal(selected, concept)
  assert.ok(render(ReadLessonButton, { concept, onLearn() {} }).includes('Read Lesson'))
})
