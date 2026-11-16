import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { createServer } from 'vite'

let server
let SkillTree
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false } })
  SkillTree = (await server.ssrLoadModule('/src/SkillTree.tsx')).default
})
after(async () => { await server?.close() })

const graph = {
  nodes: [{ id: 1, name: 'Foundation' }, { id: 2, name: 'Dependent' }, { id: 3, name: 'Independent' }],
  edges: [{ source: 1, target: 2 }],
}
const concepts = graph.nodes.map((node) => ({
  concept_id: node.id, concept_name: node.name,
  mastery_probability: 0.2, attempted: false, status: 'weak',
}))
function render(items = concepts, data = graph) {
  return renderToStaticMarkup(createElement(SkillTree, {
    graph: data, concepts: items, onPractice: () => {}, isSubmitting: false,
  }))
}

// Legend/help text repeats status names; verify state on the actual nodes.
const nodeMarkup = (html) => (html.match(/<button\b[^]*?<\/button>/g) ?? []).join('')

test('all graph concepts render as native buttons, with no unearned default percentages', () => {
  const html = nodeMarkup(render())
  assert.equal((html.match(/<button /g) ?? []).length, 3)
  for (const { name } of graph.nodes) assert.ok(html.includes(name))
  assert.ok(html.includes('Locked · Not Started'))
  assert.equal((html.match(/Ready to Learn/g) ?? []).length, 2)
  assert.ok(!html.includes('20.0%'))
  assert.ok(html.includes('data-locked="true"'))
  assert.equal((html.match(/aria-pressed="false"/g) ?? []).length, 3)
})

test('mastered prerequisite unlocks a dependent using backend status', () => {
  const html = nodeMarkup(render(concepts.map((concept) => concept.concept_id === 1
    ? { ...concept, attempted: true, status: 'mastered', mastery_probability: 0.85 }
    : concept)))
  assert.ok(html.includes('Mastered · 85.0% estimated mastery'))
  assert.ok(!html.includes('Locked · Not Started'))
  assert.equal((html.match(/Ready to Learn/g) ?? []).length, 2)
})

test('arrow starts below prerequisite and ends above dependent with an end marker', () => {
  const html = render()
  assert.ok(html.includes('d="M134,144 V160 H134 V224 H134 V240"'))
  assert.ok(html.includes('marker-end="url(#'))
})

test('empty graph provides an explicit empty state', () => {
  const html = render([], { nodes: [], edges: [] })
  assert.ok(html.includes('No concepts are available for the skill tree yet.'))
  assert.ok(!html.includes('<button '))
})

// Current eight-concept prerequisite structure, as returned by /concept-graph.
const currentGraph = {
  nodes: ['Arrays', 'Time Complexity', 'Linear Search', 'Binary Search', 'Bubble Sort', 'Merge Sort', 'Recursion', 'Sorting Fundamentals']
    .map((name, index) => ({ id: index + 1, name })),
  edges: [[1, 3], [1, 4], [1, 5], [1, 6], [1, 8], [2, 5], [3, 4], [7, 6]]
    .map(([source, target]) => ({ source, target })),
}

test('current graph keeps eight nodes and eight directed arrows with distinct sibling ports', () => {
  const html = render([], currentGraph)
  const edges = [...html.matchAll(/<g data-source="(\d+)" data-target="(\d+)"[^]*?<\/g>/g)]
  assert.equal((html.match(/<button /g) ?? []).length, 8)
  assert.equal(edges.length, 8)
  assert.equal((html.match(/marker-end=/g) ?? []).length, 8)
  assert.deepEqual(edges.map((edge) => ({ source: Number(edge[1]), target: Number(edge[2]) })), currentGraph.edges)
  const paths = edges.map((edge) => edge[0].match(/d="([^"]+)"/)[1])
  assert.equal(new Set(paths).size, 8)
  const starts = edges.filter((edge) => edge[1] === '1').map((edge) => edge[0].match(/d="M([^,]+)/)[1])
  assert.equal(new Set(starts).size, 5)
  const arrivals = edges.filter((edge) => edge[2] === '4').map((edge) => edge[0].match(/ H([\d.]+) V[\d.]+"/)[1])
  assert.equal(new Set(arrivals).size, 2)
  assert.equal(render([], currentGraph), html)
})

test('all current connector segments avoid node interiors, including the skipped layer', () => {
  const html = render([], currentGraph)
  const nodes = [...html.matchAll(/class="skill-tree-node[^]*?style="left:([\d.]+)px;top:([\d.]+)px"/g)]
    .map((match) => ({ x: Number(match[1]), y: Number(match[2]) }))
  assert.equal(nodes.length, 8)
  const paths = [...html.matchAll(/<path d="(M[^"]+)" stroke="var\(--color-primary\)"/g)]
  assert.equal(paths.length, 8)
  for (const match of paths) {
    const commands = [...match[1].matchAll(/([MVH])([\d.]+)(?:,([\d.]+))?/g)]
    let x = Number(commands[0][2])
    let y = Number(commands[0][3])
    for (const [, command, value] of commands.slice(1)) {
      const nextX = command === 'H' ? Number(value) : x
      const nextY = command === 'V' ? Number(value) : y
      for (const node of nodes) {
        const crosses = command === 'H'
          ? y > node.y && y < node.y + 120 && Math.max(x, nextX) > node.x && Math.min(x, nextX) < node.x + 220
          : x > node.x && x < node.x + 220 && Math.max(y, nextY) > node.y && Math.min(y, nextY) < node.y + 120
        assert.equal(crosses, false, `Connector ${match[1]} crosses a node`)
      }
      x = nextX
      y = nextY
    }
  }
})
