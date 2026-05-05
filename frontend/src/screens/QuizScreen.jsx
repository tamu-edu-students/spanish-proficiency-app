import { useState, useRef } from 'react'
import axios from 'axios'

const API = 'http://127.0.0.1:8000/api'

function QuizScreen({ level }) {
  const [question, setQuestion] = useState(null)
  const [selected, setSelected] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [loadingQ, setLoadingQ] = useState(false)
  const [loadingF, setLoadingF] = useState(false)

  const nextQuestionRef = useRef(null)
  const prefetchingRef  = useRef(false)

  function trackQuizActivity() {
    const activities     = JSON.parse(localStorage.getItem('activities') || '[]')
    const lastActivity   = activities[0]
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
    const recentQuiz     = lastActivity &&
      lastActivity.label === 'Grammar quiz' &&
      new Date(lastActivity.time) > fiveMinutesAgo

    if (!recentQuiz) {
      activities.unshift({
        label: 'Grammar quiz',
        color: '#EF9F27',
        time:  new Date().toISOString()
      })
      localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))
    }
  }

  async function prefetchNextQuestion() {
    if (prefetchingRef.current) return
    prefetchingRef.current = true
    try {
      const response = await axios.post(`${API}/quiz/`, { level })
      nextQuestionRef.current = response.data.question
      console.log('✓ Next question pre-loaded!')
    } catch (e) {
      console.log('Pre-fetch failed — will fetch on demand')
      nextQuestionRef.current = null
    } finally {
      prefetchingRef.current = false
    }
  }

  function startQuiz() {
    trackQuizActivity()
    getQuestion()
  }

  async function getQuestion() {
    setSelected(null)
    setFeedback(null)
    setLoadingQ(true)

    if (nextQuestionRef.current) {
      const preloaded = nextQuestionRef.current
      nextQuestionRef.current = null
      setQuestion(preloaded)
      setLoadingQ(false)
      prefetchNextQuestion()
      return
    }

    try {
      const response = await axios.post(`${API}/quiz/`, { level })
      setQuestion(response.data.question)
      prefetchNextQuestion()
    } catch (error) {
      console.error('Error fetching question:', error)
      if (error.response?.status === 500) {
        alert('Gemini is busy. Please wait a moment and try again.')
      } else {
        alert('Error getting question. Please try again.')
      }
    } finally {
      setLoadingQ(false)
    }
  }

  async function pickAnswer(option) {
    if (selected) return

    setSelected(option)

    const isCorrect   = option === question.answer
    const prevCorrect = parseInt(localStorage.getItem('quizCorrect') || '0')
    const prevTotal   = parseInt(localStorage.getItem('quizTotal')   || '0')
    const newCorrect  = prevCorrect + (isCorrect ? 1 : 0)
    const newTotal    = prevTotal + 1
    const newAccuracy = Math.round((newCorrect / newTotal) * 100)

    localStorage.setItem('quizCorrect', newCorrect.toString())
    localStorage.setItem('quizTotal',   newTotal.toString())

    // ── Show instant default feedback immediately ──
    // User sees this right away — no waiting
    const defaultFeedback = isCorrect
      ? '¡Correcto! Muy bien hecho. 🎉'
      : `Incorrecto. La respuesta correcta es: "${question.answer}"`
    setFeedback(defaultFeedback)
    setLoadingF(false)

    // ── Run progress save AND Gemini feedback in parallel ──
    // Both happen at the same time in the background
    const [_, feedbackResult] = await Promise.allSettled([

      // Save progress silently
      axios.post(`${API}/progress/`, {
        session_id: 'user_001',
        accuracy:   newAccuracy
      }).then(r => {
        if (r.data.level_up) {
          alert(`🎉 ¡Felicidades! You leveled up from ${r.data.old_level} to ${r.data.progress.level}!`)
        }
      }).catch(e => console.error('Accuracy save error:', e)),

      // Get detailed Spanish explanation from Gemini
      axios.post(`${API}/quiz/check/`, {
        question:       question.sentence,
        user_answer:    option,
        correct_answer: question.answer,
        level:          level
      })
    ])

    // Replace default feedback with Gemini's detailed explanation
    // If Gemini fails the default message stays — user never sees an error
    if (feedbackResult.status === 'fulfilled') {
      setFeedback(feedbackResult.value.data.feedback)
    }
  }

  // ── START SCREEN ─────────────────────────────────────────────
  if (!question && !loadingQ) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>

        <div style={{ fontSize: '48px', marginBottom: '16px' }}>📝</div>

        <p style={{ fontSize: '18px', fontWeight: '600', color: '#333', marginBottom: '8px' }}>
          Spanish Grammar Quiz
        </p>

        <p style={{
          fontSize: '14px', color: '#666',
          lineHeight: '1.6', marginBottom: '24px'
        }}>
          Gemini will give you a Spanish grammar question.
          Pick the correct word to complete the sentence.
          You'll get an explanation in Spanish after each answer.
        </p>

        <div style={{
          display:      'inline-block',
          background:   '#E1F5EE',
          color:        '#085041',
          borderRadius: '20px',
          padding:      '4px 14px',
          fontSize:     '13px',
          marginBottom: '24px'
        }}>
          Level: {level}
        </div>

        <br />

        <button
          onClick={startQuiz}
          style={{
            padding:      '14px 40px',
            background:   '#500000',
            color:        '#fff',
            border:       'none',
            borderRadius: '12px',
            fontSize:     '15px',
            fontWeight:   '500',
            cursor:       'pointer'
          }}
        >
          Start Quiz
        </button>

      </div>
    )
  }

  // ── LOADING SCREEN ───────────────────────────────────────────
  if (loadingQ) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
        <div style={{
          width:        '40px',
          height:       '40px',
          border:       '3px solid #e0e0e0',
          borderTop:    '3px solid #500000',
          borderRadius: '50%',
          animation:    'spin 0.8s linear infinite',
          margin:       '0 auto 16px'
        }} />
        <style>{`
          @keyframes spin {
            0%   { transform: rotate(0deg);   }
            100% { transform: rotate(360deg); }
          }
        `}</style>
        <p style={{ fontSize: '14px' }}>Generando pregunta...</p>
        <p style={{ fontSize: '12px', marginTop: '8px', color: '#999' }}>
          Gemini is creating a {level} level question
        </p>
      </div>
    )
  }

  // ── QUESTION SCREEN ──────────────────────────────────────────
  return (
    <div style={{ padding: '16px' }}>

      {/* Level badge */}
      <div style={{
        display:        'flex',
        justifyContent: 'flex-end',
        marginBottom:   '16px'
      }}>
        <span style={{
          background:   '#E1F5EE',
          color:        '#085041',
          borderRadius: '20px',
          padding:      '3px 12px',
          fontSize:     '12px',
          fontWeight:   '500'
        }}>
          Level {level}
        </span>
      </div>

      {/* Question card */}
      <div style={{
        background:   '#fff',
        border:       '1px solid #e0e0e0',
        borderRadius: '16px',
        padding:      '20px',
        marginBottom: '16px'
      }}>
        <p style={{
          fontSize:     '13px',
          color:        '#500000',
          fontWeight:   '500',
          marginBottom: '10px'
        }}>
          Fill in the blank:
        </p>
        <p style={{ fontSize: '17px', color: '#333', lineHeight: '1.6' }}>
          {question.sentence}
        </p>
      </div>

      {/* Answer options */}
      <div style={{
        display:       'flex',
        flexDirection: 'column',
        gap:           '10px',
        marginBottom:  '16px'
      }}>
        {question.options.map((option, i) => {
          let bg     = '#fff'
          let border = '#e0e0e0'
          let color  = '#333'

          if (selected) {
            if (option === question.answer) {
              bg = '#E1F5EE'; border = '#1D9E75'; color = '#085041'
            } else if (option === selected && option !== question.answer) {
              bg = '#FCEBEB'; border = '#E24B4A'; color = '#501313'
            }
          }

          return (
            <button
              key={i}
              onClick={() => pickAnswer(option)}
              disabled={!!selected}
              style={{
                padding:      '14px 16px',
                background:   bg,
                border:       `1px solid ${border}`,
                borderRadius: '12px',
                color:        color,
                fontSize:     '14px',
                textAlign:    'left',
                cursor:       selected ? 'default' : 'pointer',
                transition:   'all 0.2s',
                display:      'flex',
                alignItems:   'center',
                gap:          '10px'
              }}
            >
              <span style={{
                width:          '24px',
                height:         '24px',
                borderRadius:   '50%',
                background:     selected && option === question.answer
                  ? '#1D9E75'
                  : selected && option === selected && option !== question.answer
                    ? '#E24B4A'
                    : '#f0f0f0',
                color: selected && (option === question.answer || option === selected)
                  ? '#fff' : '#666',
                display:        'flex',
                alignItems:     'center',
                justifyContent: 'center',
                fontSize:       '12px',
                fontWeight:     '500',
                flexShrink:     0
              }}>
                {['A','B','C','D'][i]}
              </span>
              {option}
            </button>
          )
        })}
      </div>

      {/* Feedback — shows instantly then updates with Gemini explanation */}
      {selected && feedback && (
        <div style={{
          padding:      '14px',
          background:   selected === question.answer ? '#E1F5EE' : '#FCEBEB',
          border:       `1px solid ${selected === question.answer ? '#5DCAA5' : '#F09595'}`,
          borderRadius: '12px',
          marginBottom: '16px'
        }}>
          <p style={{
            fontSize:     '13px',
            fontWeight:   '500',
            color:        selected === question.answer ? '#085041' : '#501313',
            marginBottom: '4px'
          }}>
            {selected === question.answer ? '¡Correcto! 🎉' : 'Incorrecto ❌'}
          </p>
          <p style={{
            fontSize:   '13px',
            color:      selected === question.answer ? '#0F6E56' : '#7B2323',
            lineHeight: '1.5'
          }}>
            {feedback}
          </p>
        </div>
      )}

      {/* Next question — shows immediately after answer selected */}
      {selected && (
        <button
          onClick={getQuestion}
          style={{
            width:        '100%',
            padding:      '14px',
            background:   '#500000',
            color:        '#fff',
            border:       'none',
            borderRadius: '12px',
            fontSize:     '15px',
            fontWeight:   '500',
            cursor:       'pointer'
          }}
        >
          Next Question →
        </button>
      )}

    </div>
  )
}

export default QuizScreen