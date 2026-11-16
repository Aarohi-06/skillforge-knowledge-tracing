
import { useEffect, useRef, useState } from 'react'
import { prepareAttemptSubmission, submitAttempt, type AttemptResponse, type PendingAttempt } from './api/attempts'
import { fetchConcepts, type Concept } from './api/concepts'
import { fetchQuestions, type Question } from './api/questions'
import ProgressPage from './ProgressPage'
import RecommendationsSection from './RecommendationsSection'
import ConceptLearning from './ConceptLearning'

type Page = 'dashboard' | 'practice' | 'progress'
type View = Page | 'learn'

function App() {
  const [activePage, setActivePage] = useState<View>('dashboard')
  const [learningConcept, setLearningConcept] = useState<Concept | null>(null)
  const [returnPage, setReturnPage] = useState<Page>('dashboard')

  function openLesson(concept: Concept) {
    if (activePage !== 'learn') setReturnPage(activePage)
    setLearningConcept(concept)
    setActivePage('learn')
  }

  const [concepts, setConcepts] = useState<Concept[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadConcepts() {
      try {
        const data = await fetchConcepts()
        setConcepts(data)
      } catch {
        setError('Could not load concepts. Is the backend running?')
      } finally {
        setLoading(false)
      }
    }

    loadConcepts()
  }, [])

  const navigation: { id: Page; label: string; iconPath: string }[] = [
    { id: 'dashboard', label: 'Dashboard', iconPath: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z' },
    { id: 'practice', label: 'Practice', iconPath: 'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z M13 7a3 3 0 0 1 3-3h5v14h-4a4 4 0 0 0-4 3' },
    { id: 'progress', label: 'My Progress', iconPath: 'M4 20h17 M6 16v-4 M12 16V8 M18 16V4' },
  ]

  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null)
  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [questionsError, setQuestionsError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [attemptResult, setAttemptResult] = useState<AttemptResponse | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const submissionInFlight = useRef(false)
  const pendingAttempt = useRef<PendingAttempt | null>(null)
  const questionRequestId = useRef(0)

  function resetAnswer() {
    pendingAttempt.current = null
    setSelectedAnswer(null)
    setAttemptResult(null)
    setSubmissionError(null)
  }

  async function handleSubmitAnswer() {
    const question = questions[currentQuestionIndex]
    if (!question || selectedAnswer === null || submissionInFlight.current || attemptResult) return

    submissionInFlight.current = true
    setIsSubmitting(true)
    setSubmissionError(null)

    try {
      pendingAttempt.current = prepareAttemptSubmission(pendingAttempt.current, {
        student_id: 1,
        question_id: question.id,
        selected_answer: selectedAnswer,
      })
      const result = await submitAttempt(pendingAttempt.current)
      setAttemptResult(result)
    } catch (error) {
      setSubmissionError(
        `${error instanceof Error ? error.message : 'Could not submit your answer.'} Please try again.`
      )
    } finally {
      submissionInFlight.current = false
      setIsSubmitting(false)
    }
  }

  function nextQuestion() {
    if (!attemptResult || submissionInFlight.current || currentQuestionIndex >= questions.length - 1) return
    setCurrentQuestionIndex((index) => index + 1)
    resetAnswer()
  }


  async function startPractice(concept: Concept) {
    if (submissionInFlight.current) return
    const requestId = ++questionRequestId.current
    setSelectedConcept(concept)
    setQuestions([])
    setCurrentQuestionIndex(0)
    resetAnswer()
    setQuestionsLoading(true)
    setQuestionsError(null)

    try {
      const allQuestions = await fetchQuestions()
      if (requestId !== questionRequestId.current) return
      const conceptQuestions = allQuestions.filter(
        (question) => question.concept_id === concept.id
      )

      setQuestions(conceptQuestions)
    } catch {
      if (requestId === questionRequestId.current) {
        setQuestionsError('Could not load questions. Please try again.')
      }
    } finally {
      if (requestId === questionRequestId.current) setQuestionsLoading(false)
    }
  }

  function exitPractice() {
    if (submissionInFlight.current) return
    questionRequestId.current += 1
    setSelectedConcept(null)
    setQuestions([])
    setCurrentQuestionIndex(0)
    resetAnswer()
  }

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link button button-secondary">Skip to content</a>
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div>
          <h1 className="app-brand">
            SkillForge
          </h1>
          <p className="app-brand-caption">
            Forge your skills. Unlock your potential.
          </p>
        </div>

        <nav className="shell-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className="shell-nav-button"
              aria-current={activePage === item.id ? 'page' : undefined}
            >
              <svg aria-hidden="true" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d={item.iconPath} /></svg>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="shell-note">
          <p className="text-sm font-medium">Level up your DSA</p>
          <p>
            Small steps lead to stronger problem-solving skills.
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main id="main-content" tabIndex={-1} className="app-main">
        <div className="app-content">
        {activePage === 'dashboard' && (
          <div className="dashboard">
            <header className="dashboard-welcome">
              <p className="dashboard-eyebrow">YOUR LEARNING SPACE</p>
              <h2 className="mt-4 max-w-xl">Welcome to SkillForge</h2>
              <p className="mt-4 max-w-md text-muted">
                Build your DSA foundations, one concept at a time.
              </p>
            </header>

            <dl className="mt-5 grid gap-4 sm:grid-cols-3">
              {[
                { label: 'Concepts Available', value: '8' },
                { label: 'Questions Available', value: '25' },
                { label: 'Learning Mode', value: 'Adaptive' },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="dashboard-stat"
                >
                  <dt className="text-sm text-muted">{stat.label}</dt>
                  <dd className="mt-3 break-words text-3xl font-semibold tracking-tight text-ink">
                    {stat.value}
                  </dd>
                </div>
              ))}
            </dl>

            <RecommendationsSection
              onLearn={(recommendation) => openLesson(concepts.find((item) => item.id === recommendation.concept_id) ?? { id: recommendation.concept_id, name: recommendation.concept_name, description: null })}
              attemptId={attemptResult?.attempt_id}
              isSubmitting={isSubmitting}
              onPractice={(recommendation) => {
                if (submissionInFlight.current) return
                const concept = concepts.find((item) => item.id === recommendation.concept_id) ?? {
                  id: recommendation.concept_id,
                  name: recommendation.concept_name,
                  description: null,
                }
                setActivePage('practice')
                void startPractice(concept)
              }}
            />

            <div className="dashboard-practice">
              <div className="max-w-lg">
                <h3 className="font-editorial text-2xl font-medium tracking-tight text-ink">Ready to level up?</h3>
                <p className="mt-3 text-sm text-muted">
                  Start practicing DSA concepts and discover your strengths
                  and weaknesses.
                </p>
              </div>
              <button
                onClick={() => setActivePage('practice')}
                className="button button-primary shrink-0 self-start lg:self-center"
              >
                Start Practicing →
              </button>
            </div>
          </div>
        )}

        {activePage === 'practice' && (
          <div className="practice-page">
            {!selectedConcept ? (
              <>
                <header className="practice-header">
                  <h2>Practice DSA</h2>
                  <p className="mt-3 max-w-lg text-muted">
                    Choose a concept to strengthen your understanding.
                  </p>
                </header>

                {loading && (
                  <p role="status" className="practice-state">Loading concepts...</p>
                )}

                {error && (
                  <p role="alert" className="practice-state text-feedback-error">{error}</p>
                )}

                {!loading && !error && (
                  <div className="mt-8 grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
                    {concepts.map((concept) => (
                      <div
                        key={concept.id}
                        className="practice-concept-card"
                      >
                        <div aria-hidden="true" className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-lavender text-ink">
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z M13 7a3 3 0 0 1 3-3h5v14h-4a4 4 0 0 0-4 3" /></svg>
                        </div>

                        <h3 className="break-words text-xl font-semibold tracking-tight">{concept.name}</h3>

                        <p className="mt-3 mb-5 text-sm leading-relaxed text-muted">
                          {concept.description || 'Practice this DSA concept.'}
                        </p>

                        <button
                          onClick={() => startPractice(concept)}
                          className="button button-primary mt-auto self-start text-sm"
                        >
                          Practice Questions →
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="mx-auto max-w-3xl">
                <button
                  onClick={exitPractice}
                  disabled={isSubmitting}
                  className="button button-secondary mb-8 text-sm"
                >
                  ← Back to Concepts
                </button>

                <h2 className="break-words">{selectedConcept.name}</h2>
                <p className="mt-3 text-muted">
                  Test your understanding of this concept.
                </p>

                {questionsLoading && (
                  <p role="status" className="practice-state">Loading questions...</p>
                )}

                {questionsError && (
                  <p role="alert" className="practice-state text-feedback-error">{questionsError}</p>
                )}

                {!questionsLoading && !questionsError && questions.length === 0 && (
                  <p role="status" className="practice-state">
                    No questions available for this concept yet.
                  </p>
                )}

                {!questionsLoading && !questionsError && questions.length > 0 && (
                  <div className="practice-question-card" aria-busy={isSubmitting}>
                    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                      <span className="text-sm font-medium text-muted">
                        Question {currentQuestionIndex + 1} of {questions.length}
                      </span>

                      <span className="rounded-full bg-ice px-3 py-1 text-xs font-medium text-ink">
                        {questions[currentQuestionIndex].difficulty}
                      </span>
                    </div>

                    <h3 id="practice-question-title" className="break-words text-xl leading-relaxed font-semibold sm:text-2xl">
                      {questions[currentQuestionIndex].title}
                    </h3>

                    {questions[currentQuestionIndex].description && (
                      <p className="mt-4 whitespace-pre-wrap break-words leading-relaxed text-muted">
                        {questions[currentQuestionIndex].description}
                      </p>
                    )}

                    <div className="mt-8 space-y-3" role="group" aria-labelledby="practice-question-title">
                      {questions[currentQuestionIndex].options.map((option, index) => (
                        <button
                          key={index}
                          onClick={() => setSelectedAnswer(index)}
                          disabled={isSubmitting || attemptResult !== null}
                          aria-pressed={selectedAnswer === index}
                          className="practice-option"
                        >
                          <span className="practice-option-letter" aria-hidden="true">
                            {String.fromCharCode(65 + index)}
                          </span>
                          <span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{option}</span>
                          {selectedAnswer === index && <span className="practice-option-selected">Selected</span>}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={handleSubmitAnswer}
                      disabled={selectedAnswer === null || isSubmitting || attemptResult !== null}
                      className="button button-primary mt-8 w-full"
                    >
                      {isSubmitting ? 'Submitting...' : attemptResult ? 'Answer Submitted' : 'Submit Answer'}
                    </button>

                    {submissionError && (
                      <p role="alert" className="mt-4 text-sm text-feedback-error">
                        {submissionError}
                      </p>
                    )}

                    {attemptResult && (
                      <div role="status" className="practice-feedback" data-correct={attemptResult.is_correct}>
                        <p className="flex items-center gap-2 font-semibold">
                          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0"><circle cx="12" cy="12" r="9" /><path d={attemptResult.is_correct ? 'M8 12l3 3 5-6' : 'M9 9l6 6 M15 9l-6 6'} /></svg>
                          {attemptResult.is_correct ? 'Correct!' : 'Incorrect.'}
                        </p>
                        <p className="mt-3 text-sm text-ink">
                          Updated BKT mastery: {(attemptResult.mastery_probability * 100).toFixed(1)}%
                        </p>
                        {currentQuestionIndex < questions.length - 1 ? (
                          <button
                            onClick={nextQuestion}
                            className="button button-primary mt-5"
                          >
                            Next Question
                          </button>
                        ) : (
                          <p className="mt-5 text-sm font-medium text-ink">
                            You have completed all questions for this concept.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}



        {activePage === 'learn' && learningConcept && (
          <ConceptLearning key={learningConcept.id} concept={learningConcept} concepts={concepts} onSelect={openLesson} backLabel={returnPage === 'progress' ? 'My Progress' : returnPage === 'practice' ? 'Practice' : 'Dashboard'}
            onBack={() => setActivePage(returnPage)} isSubmitting={isSubmitting} attemptId={attemptResult?.attempt_id}
            onPractice={(concept) => { if (submissionInFlight.current) return; setActivePage('practice'); void startPractice(concept) }} />
        )}

        {activePage === 'progress' && (
          <ProgressPage
            onLearn={openLesson}
            attemptId={attemptResult?.attempt_id}
            isSubmitting={isSubmitting}
            onPractice={(concept) => {
              if (submissionInFlight.current) return
              setActivePage('practice')
              void startPractice(concept)
            }}
          />
        )}
        </div>
      </main>
    </div>
  )
}

export default App
