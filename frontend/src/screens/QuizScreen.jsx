import { useState } from 'react'
import axios from 'axios'

const API     = '/api'
const TOTAL_Q = 10

function QuizScreen({ level, sessionId }) {
  const [questions, setQuestions]       = useState([])
  const [questionNum, setQuestionNum]   = useState(0)   // 0 = start screen
  const [selected, setSelected]         = useState(null)
  const [feedback, setFeedback]         = useState(null)
  const [sessionScore, setSessionScore] = useState(0)
  const [quizDone, setQuizDone]         = useState(false)
  const [loading, setLoading]           = useState(false)

  const currentQuestion = questions[questionNum - 1] || null

  function shuffleQuestionOptions(question) {
    if (!question || !Array.isArray(question.options)) return question

    const options = [...question.options]
    for (let i = options.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[options[i], options[j]] = [options[j], options[i]]
    }

    return { ...question, options }
  }

  function trackQuizActivity() {
    const activities     = JSON.parse(localStorage.getItem('activities') || '[]')
    const lastActivity   = activities[0]
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
    const recentQuiz     = lastActivity &&
      lastActivity.label === 'Grammar quiz' &&
      new Date(lastActivity.time) > fiveMinutesAgo
    if (!recentQuiz) {
      activities.unshift({ label: 'Grammar quiz', color: '#EF9F27', time: new Date().toISOString() })
      localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))
    }
  }

  async function startQuiz() {
    setLoading(true)
    setSessionScore(0)
    setQuizDone(false)
    setSelected(null)
    setFeedback(null)
    trackQuizActivity()

    try {
      const response = await axios.post(`${API}/quiz/batch/`, { level, count: TOTAL_Q })
      const qs = response.data.questions
      if (!qs || qs.length === 0) throw new Error('No questions returned')
      setQuestions(qs.map(shuffleQuestionOptions))
      setQuestionNum(1)
    } catch (error) {
      console.error('Error loading quiz:', error)
      alert('Could not load quiz. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function pickAnswer(option) {
    if (selected) return
    setSelected(option)

    const isCorrect  = option === currentQuestion.answer
    const newSession = sessionScore + (isCorrect ? 1 : 0)
    setSessionScore(newSession)

    // Update cumulative accuracy
    const prevCorrect = parseInt(localStorage.getItem('quizCorrect') || '0')
    const prevTotal   = parseInt(localStorage.getItem('quizTotal')   || '0')
    const newCorrect  = prevCorrect + (isCorrect ? 1 : 0)
    const newTotal    = prevTotal + 1
    const newAccuracy = Math.round((newCorrect / newTotal) * 100)
    localStorage.setItem('quizCorrect', newCorrect.toString())
    localStorage.setItem('quizTotal',   newTotal.toString())

    // Show instant feedback from pre-generated explanation
    setFeedback(isCorrect
      ? (currentQuestion.explanation || 'Correcto! Muy bien hecho.')
      : `Incorrecto. La respuesta correcta es: "${currentQuestion.answer}". ${currentQuestion.explanation || ''}`)

    // Save accuracy in background
    axios.post(`${API}/progress/`, {
      session_id: sessionId,
      accuracy:   newAccuracy
    }).then(r => {
      if (r.data.level_up) {
        alert(`Felicidades! You leveled up from ${r.data.old_level} to ${r.data.progress.level}!`)
      }
    }).catch(e => console.error('Accuracy save error:', e))
  }

  function nextQuestion() {
    if (questionNum >= TOTAL_Q) {
      setQuizDone(true)
    } else {
      setQuestionNum(q => q + 1)
      setSelected(null)
      setFeedback(null)
    }
  }

  // START SCREEN
  if (questionNum === 0 && !loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>📝</div>
        <p style={{ fontSize: '18px', fontWeight: '600', color: '#333', marginBottom: '8px' }}>
          Spanish Grammar Quiz
        </p>
        <p style={{ fontSize: '14px', color: '#666', lineHeight: '1.6', marginBottom: '16px' }}>
          Answer 10 questions. Pick the correct word to complete each sentence.
          You will get a Spanish explanation after each answer.
        </p>
        <div style={{ display: 'inline-block', background: '#E1F5EE', color: '#085041', borderRadius: '20px', padding: '4px 14px', fontSize: '13px', marginBottom: '24px' }}>
          Level: {level}
        </div>
        <br />
        <button
          onClick={startQuiz}
          style={{ padding: '14px 40px', background: '#500000', color: '#fff', border: 'none', borderRadius: '12px', fontSize: '15px', fontWeight: '500', cursor: 'pointer' }}
        >
          Start Quiz
        </button>
      </div>
    )
  }

  // LOADING SCREEN — only shown once at the start
  if (loading) {
    return (
      <div style={{ padding: '60px 24px', textAlign: 'center', color: '#666' }}>
        <div style={{ width: '48px', height: '48px', border: '4px solid #f0e8e8', borderTop: '4px solid #500000', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 24px' }} />
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
        <p style={{ fontSize: '16px', fontWeight: '600', color: '#500000', marginBottom: '8px' }}>
          Preparing your quiz...
        </p>
        <p style={{ fontSize: '13px', color: '#999' }}>
          Gemini is generating 10 {level} level questions
        </p>
      </div>
    )
  }

  // SCORE SCREEN
  if (quizDone) {
    const pct     = Math.round((sessionScore / TOTAL_Q) * 100)
    const emoji   = pct >= 80 ? '🎉' : pct >= 50 ? '👍' : '💪'
    const message = pct >= 80
      ? 'Excellent work! Muy bien!'
      : pct >= 50
      ? 'Good effort! Keep practicing.'
      : 'Keep going, practice makes perfect!'

    return (
      <div style={{ padding: '32px 24px', textAlign: 'center' }}>
        <div style={{ fontSize: '56px', marginBottom: '12px' }}>{emoji}</div>
        <p style={{ fontFamily: "'Oswald', sans-serif", fontSize: '22px', fontWeight: '700', color: '#500000', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Quiz Complete
        </p>
        <p style={{ fontSize: '14px', color: '#666', marginBottom: '28px' }}>{message}</p>

        <div style={{
          width: '120px', height: '120px', borderRadius: '50%',
          background: pct >= 80 ? '#E1F5EE' : pct >= 50 ? '#FFF8E1' : '#FCEBEB',
          border: `4px solid ${pct >= 80 ? '#1D9E75' : pct >= 50 ? '#EF9F27' : '#E24B4A'}`,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 28px'
        }}>
          <p style={{ fontSize: '32px', fontWeight: '700', color: '#333', lineHeight: 1 }}>
            {sessionScore}/{TOTAL_Q}
          </p>
          <p style={{ fontSize: '13px', color: '#666', marginTop: '4px' }}>{pct}%</p>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '24px', marginBottom: '32px' }}>
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: '22px', fontWeight: '700', color: '#1D9E75' }}>{sessionScore}</p>
            <p style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Correct</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: '22px', fontWeight: '700', color: '#E24B4A' }}>{TOTAL_Q - sessionScore}</p>
            <p style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Incorrect</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <p style={{ fontSize: '22px', fontWeight: '700', color: '#500000' }}>{pct}%</p>
            <p style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Score</p>
          </div>
        </div>

        <button
          onClick={startQuiz}
          style={{ width: '100%', maxWidth: '300px', padding: '14px', background: '#500000', color: '#fff', border: 'none', borderRadius: '12px', fontSize: '15px', fontWeight: '500', cursor: 'pointer' }}
        >
          Practice Again
        </button>
      </div>
    )
  }

  // QUESTION SCREEN — no loading, instant
  return (
    <div style={{ padding: '16px' }}>

      {/* Progress bar */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '12px', color: '#888', fontFamily: "'Open Sans', sans-serif" }}>
            Question {questionNum} of {TOTAL_Q}
          </span>
          <span style={{ fontSize: '12px', color: '#500000', fontWeight: '600', fontFamily: "'Open Sans', sans-serif" }}>
            {sessionScore} correct
          </span>
        </div>
        <div style={{ height: '6px', background: '#f0e8e8', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${((questionNum - 1) / TOTAL_Q) * 100}%`,
            background: '#500000',
            borderRadius: '3px',
            transition: 'width 0.3s ease'
          }} />
        </div>
      </div>

      {/* Level badge */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
        <span style={{ background: '#E1F5EE', color: '#085041', borderRadius: '20px', padding: '3px 12px', fontSize: '12px', fontWeight: '500' }}>
          Level {level}
        </span>
      </div>

      {/* Question card */}
      <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '16px', padding: '20px', marginBottom: '16px' }}>
        <p style={{ fontSize: '13px', color: '#500000', fontWeight: '500', marginBottom: '10px' }}>
          Fill in the blank:
        </p>
        <p style={{ fontSize: '17px', color: '#333', lineHeight: '1.6' }}>
          {currentQuestion.sentence}
        </p>
      </div>

      {/* Answer options */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
        {currentQuestion.options.map((option, i) => {
          let bg = '#fff', border = '#e0e0e0', color = '#333'
          if (selected) {
            if (option === currentQuestion.answer)                             { bg = '#E1F5EE'; border = '#1D9E75'; color = '#085041' }
            else if (option === selected && option !== currentQuestion.answer) { bg = '#FCEBEB'; border = '#E24B4A'; color = '#501313' }
          }
          return (
            <button
              key={i}
              onClick={() => pickAnswer(option)}
              disabled={!!selected}
              style={{ padding: '14px 16px', background: bg, border: `1px solid ${border}`, borderRadius: '12px', color, fontSize: '14px', textAlign: 'left', cursor: selected ? 'default' : 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '10px' }}
            >
              <span style={{
                width: '24px', height: '24px', borderRadius: '50%', flexShrink: 0,
                background: selected && option === currentQuestion.answer ? '#1D9E75'
                  : selected && option === selected && option !== currentQuestion.answer ? '#E24B4A' : '#f0f0f0',
                color: selected && (option === currentQuestion.answer || option === selected) ? '#fff' : '#666',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: '500'
              }}>
                {['A','B','C','D'][i]}
              </span>
              {option}
            </button>
          )
        })}
      </div>

      {/* Feedback */}
      {selected && feedback && (
        <div style={{ padding: '14px', background: selected === currentQuestion.answer ? '#E1F5EE' : '#FCEBEB', border: `1px solid ${selected === currentQuestion.answer ? '#5DCAA5' : '#F09595'}`, borderRadius: '12px', marginBottom: '16px' }}>
          <p style={{ fontSize: '13px', fontWeight: '500', color: selected === currentQuestion.answer ? '#085041' : '#501313', marginBottom: '4px' }}>
            {selected === currentQuestion.answer ? 'Correcto! 🎉' : 'Incorrecto ❌'}
          </p>
          <p style={{ fontSize: '13px', color: selected === currentQuestion.answer ? '#0F6E56' : '#7B2323', lineHeight: '1.5' }}>
            {feedback}
          </p>
        </div>
      )}

      {/* Next / Finish button */}
      {selected && (
        <button
          onClick={nextQuestion}
          style={{ width: '100%', padding: '14px', background: '#500000', color: '#fff', border: 'none', borderRadius: '12px', fontSize: '15px', fontWeight: '500', cursor: 'pointer' }}
        >
          {questionNum >= TOTAL_Q ? 'See Results' : 'Next Question'}
        </button>
      )}

    </div>
  )
}

export default QuizScreen