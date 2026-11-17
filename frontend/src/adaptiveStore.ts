import { adaptiveApi, AdaptiveError, type AdaptiveAnswer, type AdaptiveFeedback, type AdaptiveProgress, type AdaptiveResults } from './api/adaptive.ts'
import type { Question } from './api/questions.ts'

interface Pending { selectionReason: string | null; sessionId: string; position: number; total: number; question: Question; answer: AdaptiveAnswer }
interface Cache { version: 1; student: number; sessionId: string | null; pending: Pending | null; restartId: string | null }
export interface AdaptiveState {
  session: AdaptiveProgress | null; question: Question | null; selected: number | null
  feedback: AdaptiveFeedback | null; results: AdaptiveResults | null
  busy: boolean; error: string | null; canReconcile: boolean; storageWarning: boolean; pendingAnswer: boolean
  selectionReason: string | null
  totalQuestions: number | null
}
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value)

export function createAdaptiveStore(student = 1, api = adaptiveApi, storage?: Pick<Storage, 'getItem' | 'setItem'>) {
  const key = `skillforge:adaptive:${student}:v1`
  let cache: Cache = { version: 1, student, sessionId: null, pending: null, restartId: null }
  let warning = false
  try {
    storage ??= typeof localStorage === 'undefined' ? undefined : localStorage
    const raw = storage?.getItem(key)
    if (raw) {
      const value = JSON.parse(raw) as Cache
      if (value.version !== 1 || value.student !== student || (value.sessionId !== null && !uuid(value.sessionId)) || (value.restartId !== null && !uuid(value.restartId))) throw new Error('Invalid cache')
      if (value.pending !== null) {
        const p = value.pending
        if (!Number.isInteger(p.question.id) || p.question.id <= 0 || !Number.isInteger(p.question.concept_id) || p.question.concept_id <= 0 || typeof p.question.title !== 'string' || (p.question.description !== null && typeof p.question.description !== 'string') || typeof p.question.difficulty !== 'string' || !Array.isArray(p.question.options)) throw new Error('Invalid cached question')
        if (p.selectionReason !== null && typeof p.selectionReason !== 'string') throw new Error('Invalid cached selection reason')
        if (!uuid(p.sessionId) || !uuid(p.answer.submission_id) || p.answer.question_id !== p.question.id || !Number.isInteger(p.total) || p.total < 1 || !Number.isInteger(p.position) || p.position < 0 || p.position >= p.total || !Number.isInteger(p.answer.selected_answer) || p.answer.selected_answer < 0 || p.answer.selected_answer >= p.question.options.length || !p.question.options.every((option) => typeof option === 'string')) throw new Error('Invalid pending answer')
      }
      cache = value
    }
  } catch { warning = true }
  let state: AdaptiveState = { session: null, question: null, selected: null, feedback: null, results: null, busy: false, error: null, canReconcile: false, storageWarning: warning, pendingAnswer: cache.pending !== null, totalQuestions: null, selectionReason: null }
  const listeners = new Set<() => void>()
  let controller: AbortController | null = null
  let lastAction: (() => Promise<void>) | null = null
  const update = (patch: Partial<AdaptiveState>) => { state = { ...state, ...patch }; listeners.forEach((notify) => notify()) }
  const persist = () => {
    try { if (storage) storage.setItem(key, JSON.stringify(cache)); else update({ storageWarning: true }) }
    catch { update({ storageWarning: true }) }
    update({ pendingAnswer: cache.pending !== null })
  }
  const run = async (task: (signal: AbortSignal, check: () => void) => Promise<void>) => {
    if (state.busy) return
    const current = new AbortController(); controller = current
    const check = () => { if (current.signal.aborted) throw new DOMException('Cancelled', 'AbortError') }
    update({ busy: true, error: null, canReconcile: false })
    try { await task(current.signal, check) }
    catch (error) {
      if (!current.signal.aborted) update({ error: error instanceof Error ? error.message : 'Could not load the assessment. Please try again.', canReconcile: error instanceof AdaptiveError && [404, 409].includes(error.status) })
    } finally { if (!current.signal.aborted) update({ busy: false }) }
  }
  const accept = async (session: AdaptiveProgress, signal: AbortSignal, check: () => void) => {
    check()
    if (session.student_id !== student) throw new Error('Assessment response did not match this student.')
    let completed: AdaptiveResults | null = null
    if (session.status === 'completed') {
      const results = await api.results(student, session.session_id, signal); check()
      if (results.session_id !== session.session_id || results.student_id !== student) throw new Error('Results did not match the assessment.')
      completed = results
    }
    check(); cache.sessionId = session.session_id; persist()
    update({ session, question: session.next_question, selected: null, feedback: null, results: completed, totalQuestions: session.target_questions, selectionReason: session.selection_reason })
  }
  const replay = async (pending: Pending, signal: AbortSignal, check: () => void) => {
    const result = await api.answer(student, pending.sessionId, pending.answer, signal); check()
    if (result.session_id !== pending.sessionId || result.position !== pending.position || result.feedback.student_id !== student || result.feedback.question_id !== pending.question.id || result.feedback.selected_answer !== pending.answer.selected_answer) throw new Error('Feedback did not match the submitted adaptive answer.')
    update({ question: pending.question, selected: pending.answer.selected_answer, feedback: result, results: null, totalQuestions: pending.total, selectionReason: pending.selectionReason })
  }
  const store = {
    getSnapshot: () => state,
    subscribe: (notify: () => void) => { listeners.add(notify); return () => { listeners.delete(notify) } },
    cancel: () => { controller?.abort(); update({ busy: false }) },
    select: (index: number) => { if (!state.busy && !state.feedback && !cache.pending && state.session?.current_question_eligible === true && state.question && index >= 0 && index < state.question.options.length) update({ selected: index }) },
    async open() {
      if (state.busy) return
      lastAction = () => store.open()
      await run(async (signal, check) => {
        if (cache.restartId) {
          const session = await api.restart(student, cache.restartId, signal); check()
          cache.pending = null; await accept(session, signal, check); cache.restartId = null; persist()
        } else if (cache.pending) {
          await replay(cache.pending, signal, check)
        } else {
          // /start is authoritative for the current session, including a restart
          // in another tab. A stale local session ID never selects a question.
          const session = await api.start(student, signal); check(); await accept(session, signal, check)
        }
      })
    },
    async submit() {
      if (state.busy || state.feedback || !state.question || state.selected === null || !state.session) return
      if (!cache.pending && state.session.current_question_eligible !== true) return
      lastAction = () => store.submit()
      const pending = cache.pending ?? { sessionId: state.session.session_id, position: state.session.next_position!, total: state.session.target_questions, selectionReason: state.session.selection_reason, question: state.question,
        answer: { question_id: state.question.id, selected_answer: state.selected, submission_id: crypto.randomUUID() } }
      cache.pending = pending; persist()
      await run((signal, check) => replay(pending, signal, check))
    },
    async next() {
      if (state.busy || !state.feedback) return
      lastAction = () => store.next()
      const sessionId = state.feedback.session_id
      await run(async (signal, check) => {
        const session = await api.progress(student, sessionId, signal); check()
        if (session.session_id !== sessionId) throw new Error('Progress did not match this assessment.')
        cache.pending = null; persist(); await accept(session, signal, check)
      })
    },
    async restart() {
      if (state.busy) return
      lastAction = () => store.restart()
      cache.restartId ??= crypto.randomUUID(); persist()
      await run(async (signal, check) => {
        const session = await api.restart(student, cache.restartId!, signal); check()
        cache.pending = null; await accept(session, signal, check); cache.restartId = null; persist()
      })
    },
    async reconcile() {
      if (state.busy) return
      lastAction = () => store.reconcile()
      await run(async (signal, check) => {
        const session = await api.start(student, signal); check()
        cache.pending = null; cache.restartId = null; persist(); await accept(session, signal, check)
      })
    },
    retry: async () => { await lastAction?.() },
  }
  return store
}
