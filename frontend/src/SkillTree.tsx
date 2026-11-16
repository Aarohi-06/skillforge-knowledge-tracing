import { useId, useState } from 'react'
import type { ConceptGraph } from './api/conceptGraph'
import type { ConceptProgress } from './api/progress'
import type { Concept } from './api/concepts'
import { skillTreeDisplay } from './masteryDisplay'
import { unmetPrerequisites } from './practiceAccess'

const styles = {
  'Not Started': 'bg-paper text-ink',
  Weak: 'bg-blush text-ink',
  Learning: 'bg-lavender text-ink',
  Mastered: 'bg-ice text-ink',
}

interface Props {
  graph: ConceptGraph
  concepts: ConceptProgress[]
  onPractice: (concept: Concept) => void
  onLearn: (concept: Concept) => void
  isSubmitting: boolean
}

export function ReadLessonButton({ concept, onLearn }: { concept: Concept; onLearn: Props['onLearn'] }) {
  return <button className="button button-secondary mt-5 mr-3" onClick={() => onLearn(concept)}>Read Lesson</button>
}

export default function SkillTree({ graph, concepts, onPractice, onLearn, isSubmitting }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const markerId = useId()
  const progress = new Map(concepts.map((concept) => [concept.concept_id, concept]))
  const prerequisites = (id: number) => graph.edges.filter((edge) => edge.target === id).map((edge) => edge.source)
  // Status is classified by the backend's shared mastery thresholds.
  const unmet = (id: number) => unmetPrerequisites(id, graph, concepts)
  const label = (id: number): keyof typeof styles => {
    const item = progress.get(id)
    if (!item?.attempted) return 'Not Started'
    return { weak: 'Weak', learning: 'Learning', mastered: 'Mastered' }[item.status] as keyof typeof styles
  }

  // Layer a small DAG by its longest prerequisite path; keep isolated nodes.
  const depths = new Map<number, number>()
  for (let pass = 0; pass < graph.nodes.length; pass++) {
    for (const node of graph.nodes) {
      if (depths.has(node.id)) continue
      const parents = prerequisites(node.id)
      if (parents.every((id) => depths.has(id))) {
        depths.set(node.id, parents.length ? Math.max(...parents.map((id) => depths.get(id)!)) + 1 : 0)
      }
    }
  }
  // Keep every node inspectable even if stored relationships contain a cycle.
  const cyclic = depths.size < graph.nodes.length
  const positions = new Map<number, { x: number; y: number }>()
  const rows = new Map<number, number>()
  for (const node of graph.nodes) {
    const depth = depths.get(node.id) ?? graph.nodes.length
    const row = rows.get(depth) ?? 0
    rows.set(depth, row + 1)
    positions.set(node.id, { x: 24 + row * 260, y: 24 + depth * 220 })
  }
  const width = Math.max(300, ...Array.from(positions.values(), (point) => point.x + 244))
  const height = Math.max(160, ...Array.from(positions.values(), (point) => point.y + 144))
  const selected = graph.nodes.find((node) => node.id === selectedId)
  const selectedProgress = selected ? progress.get(selected.id) : undefined
  const blocked = selected ? unmet(selected.id) : []
  const name = (id: number) => graph.nodes.find((node) => node.id === id)?.name ?? `Concept ${id}`

  const connectorPath = (edge: ConceptGraph['edges'][number]) => {
    const source = positions.get(edge.source)
    const target = positions.get(edge.target)
    if (!source || !target) return null
    const byPosition = (a: number, b: number) => {
      const first = positions.get(a)!
      const second = positions.get(b)!
      return first.x - second.x || first.y - second.y || a - b
    }
    const outgoing = graph.edges.filter((item) => item.source === edge.source)
      .map((item) => item.target).sort(byPosition)
    const incoming = graph.edges.filter((item) => item.target === edge.target)
      .map((item) => item.source).sort(byPosition)
    const exitIndex = outgoing.indexOf(edge.target)
    const entryIndex = incoming.indexOf(edge.source)
    // Give each sibling edge its own port and horizontal lane.
    const startX = source.x + (exitIndex + 1) * 220 / (outgoing.length + 1)
    const endX = target.x + (entryIndex + 1) * 220 / (incoming.length + 1)
    const exitY = source.y + 120 + 16 + exitIndex * 10
    const entryY = target.y - 20 - entryIndex * 10
    // Skipping a layer must go around intervening cards, never through them.
    const laneX = outgoing.length > 1 || incoming.length > 1 || target.y - source.y > 220 || target.y <= source.y
      ? source.x + 228 + exitIndex * 6
      : endX
    return `M${startX},${source.y + 120} V${exitY} H${laneX} V${entryY} H${endX} V${target.y - 4}`
  }

  return (
    <section aria-labelledby="skill-tree-heading" className="skill-tree">
      <h3 id="skill-tree-heading" className="font-editorial text-2xl font-medium tracking-tight sm:text-3xl">Skill Tree</h3>
      <p className="mt-3 max-w-2xl text-sm text-muted">Follow the arrows from prerequisite to dependent. Select a concept to explore its mastery and prerequisites.</p>
      <div aria-label="Mastery legend" className="mt-5 flex flex-wrap gap-2 text-xs font-medium">
        <span className="rounded-full border border-line bg-paper px-3 py-1">Not Started</span>
        <span className="rounded-full border border-line bg-blush px-3 py-1">Weak</span>
        <span className="rounded-full border border-line bg-lavender px-3 py-1">Learning</span>
        <span className="rounded-full border border-line bg-ice px-3 py-1">Mastered</span>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted">Unattempted concepts show Ready to Learn when unlocked, or Locked · Not Started when prerequisites are unmet. All immediate prerequisites must be mastered to unlock a concept.</p>
      {cyclic && <p role="status" className="mt-4 text-feedback-warning">Some prerequisite relationships form a cycle; those concepts appear in the final row.</p>}
      {graph.nodes.length === 0 ? <p role="status" className="mt-6 text-muted">No concepts are available for the skill tree yet.</p> : (
        <div className="skill-tree-canvas" tabIndex={0} role="region" aria-label="Scrollable prerequisite skill tree">
          <div className="relative" style={{ width, height }}>
            <svg width={width} height={height} className="pointer-events-none absolute inset-0" aria-hidden="true">
              <defs><marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--color-primary)" /></marker></defs>
              {graph.edges.map((edge) => {
                const path = connectorPath(edge)
                if (!path) return null
                return (
                  <g key={`${edge.source}-${edge.target}`} data-source={edge.source} data-target={edge.target} fill="none" strokeLinejoin="round">
                    {/* A canvas-colored halo separates unavoidable line crossings. */}
                    <path d={path} stroke="var(--color-snow)" strokeWidth="6" />
                    <path d={path} stroke="var(--color-primary)" strokeWidth="2" markerEnd={`url(#${markerId})`} />
                  </g>
                )
              })}
            </svg>
            {graph.nodes.map((node) => {
              const point = positions.get(node.id)!
              const state = label(node.id)
              return (
                <button key={node.id} onClick={() => setSelectedId(node.id)} aria-pressed={selectedId === node.id}
                  className={`skill-tree-node ${styles[state]}`}
                  data-locked={unmet(node.id).length > 0}
                  style={{ left: point.x, top: point.y }}>
                  <span className="line-clamp-2 break-words font-semibold leading-snug">{node.name}</span>
                  <span className="mt-1 text-xs leading-relaxed">{skillTreeDisplay(progress.get(node.id), unmet(node.id).length > 0)}</span>
                  {progress.get(node.id)?.attempted && <span className="text-xs text-muted">{unmet(node.id).length ? 'Locked — unmet prerequisites' : 'Unlocked'}</span>}
                </button>
              )
            })}
          </div>
        </div>
      )}
      {selected ? (
        <div className="skill-tree-details" aria-live="polite">
          <h4 className="break-words text-xl font-semibold tracking-tight">{selected.name}</h4>
          <p className="mt-2">{skillTreeDisplay(selectedProgress, blocked.length > 0)}</p>
          <p className="mt-3 text-sm text-muted">Attempted: {selectedProgress ? (selectedProgress.attempted ? 'Yes' : 'No') : 'Unavailable'}</p>
          <p className="mt-3 break-words text-sm text-muted">Immediate prerequisites: {prerequisites(selected.id).map((id) => `${name(id)} (${progress.get(id)?.status === 'mastered' ? 'Mastered' : 'Not mastered'})`).join(', ') || 'None'}</p>
          <p id="skill-tree-practice-status" className="mt-3 break-words text-sm text-muted">{blocked.length ? `Locked. Master these prerequisites first: ${blocked.map(name).join(', ')}.` : 'Unlocked. All immediate prerequisites are satisfied.'}{isSubmitting ? ' Please wait while your answer is saved.' : ''}</p>
          <ReadLessonButton concept={{ id: selected.id, name: selected.name, description: null }} onLearn={onLearn} />
          <button disabled={blocked.length > 0 || !selectedProgress || isSubmitting} aria-describedby="skill-tree-practice-status"
            onClick={() => onPractice({ id: selected.id, name: selected.name, description: null })}
            className="button button-primary mt-5">
            {blocked.length > 0 && <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-2 inline-block h-4 w-4"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>}
            {blocked.length > 0 ? 'Practice Locked' : 'Practice'}
          </button>
        </div>
      ) : <p className="mt-4 text-sm text-muted">Choose a node with your mouse or Tab and Enter to view its prerequisites and mastery. Scroll horizontally on smaller screens.</p>}
    </section>
  )
}
