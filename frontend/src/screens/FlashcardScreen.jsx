import { useState } from 'react'
import axios from 'axios'

const API = 'http://127.0.0.1:8000/api'

function FlashcardScreen({ level }) {
  const [cards, setCards]               = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped]           = useState(false)
  const [topic, setTopic]               = useState('daily life')
  const [loading, setLoading]           = useState(false)
  const [done, setDone]                 = useState(false)
  const [score, setScore]               = useState({ good: 0, hard: 0, again: 0 })

  const topics = [
    'daily life', 'food & drink', 'travel',
    'work & office', 'family', 'weather',
    'sports', 'technology', 'shopping', 'health'
  ]

  // ── Generate cards from Gemini ──────────────────────────────
  async function generateCards() {
    setLoading(true)
    setDone(false)
    setCurrentIndex(0)
    setFlipped(false)
    setScore({ good: 0, hard: 0, again: 0 })

    try {
      const response = await axios.post(`${API}/flashcards/`, {
        topic:      topic,
        level:      level,
        session_id: 'user_001'
      })
      setCards(response.data.cards)

      // ── Track activity in localStorage ──
      const activities = JSON.parse(localStorage.getItem('activities') || '[]')
      activities.unshift({
        label: 'Flashcard session',
        color: '#1D9E75',
        time:  new Date().toISOString()
      })
      localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))

    } catch (error) {
      console.error('Error generating cards:', error)
      alert('Error generating cards. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Rate a card ──────────────────────────────────────────────
  async function rateCard(rating) {
    setScore(prev => ({ ...prev, [rating]: prev[rating] + 1 }))

    // If user knew the word — save it as learned
    if (rating === 'good') {
      try {
        const current  = parseInt(localStorage.getItem('wordsLearned') || '0')
        const newCount = current + 1
        localStorage.setItem('wordsLearned', newCount.toString())

        const r = await axios.post(`${API}/progress/`, {
          session_id:    'user_001',
          words_learned: newCount
        })

        // Check if user leveled up
        if (r.data.level_up) {
          alert(`🎉 ¡Felicidades! You leveled up from ${r.data.old_level} to ${r.data.progress.level}!`)
        }

      } catch (e) {
        console.error('Words learned save error:', e)
      }
    }

    if (currentIndex + 1 >= cards.length) {
      setDone(true)
    } else {
      setCurrentIndex(prev => prev + 1)
      setFlipped(false)
    }
  }

  const card = cards[currentIndex]

  // ── TOPIC PICKER SCREEN ──────────────────────────────────────
  if (cards.length === 0) {
    return (
      <div style={{ padding: '20px' }}>

        <p style={{
          fontSize: '14px', color: '#666',
          marginBottom: '16px', lineHeight: '1.5'
        }}>
          Choose a topic and generate vocabulary cards.
          Flip each card to see the translation, then rate how well you knew it.
        </p>

        <p style={{ fontSize: '13px', fontWeight: '500', marginBottom: '8px' }}>
          Choose a topic:
        </p>
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '20px'
        }}>
          {topics.map(t => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              style={{
                padding:     '6px 12px',
                borderRadius: '20px',
                border:      '1px solid',
                borderColor: topic === t ? '#500000' : '#e0e0e0',
                background:  topic === t ? '#500000' : '#fff',
                color:       topic === t ? '#fff'    : '#666',
                fontSize:    '12px',
                cursor:      'pointer'
              }}
            >
              {t}
            </button>
          ))}
        </div>

        <p style={{ fontSize: '13px', fontWeight: '500', marginBottom: '8px' }}>
          Or type your own topic:
        </p>
        <input
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="e.g. animals, colors, emotions..."
          style={{
            width: '100%', padding: '10px 14px',
            border: '1px solid #e0e0e0', borderRadius: '10px',
            fontSize: '14px', marginBottom: '20px', outline: 'none'
          }}
        />

        <button
          onClick={generateCards}
          disabled={loading || !topic.trim()}
          style={{
            width:        '100%',
            padding:      '14px',
            background:   loading ? '#ccc' : '#500000',
            color:        '#fff',
            border:       'none',
            borderRadius: '12px',
            fontSize:     '15px',
            fontWeight:   '500',
            cursor:       loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Generating cards...' : 'Generate Cards'}
        </button>

      </div>
    )
  }

  // ── RESULTS SCREEN ───────────────────────────────────────────
  if (done) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>

        <div style={{ fontSize: '40px', marginBottom: '12px' }}>🎉</div>

        <p style={{ fontSize: '18px', fontWeight: '500', marginBottom: '6px' }}>
          ¡Sesión completada!
        </p>
        <p style={{ fontSize: '13px', color: '#666', marginBottom: '24px' }}>
          You went through all {cards.length} cards
        </p>

        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
          gap: '10px', marginBottom: '24px'
        }}>
          {[
            { label: 'Good',  value: score.good,  color: '#1D9E75', bg: '#E1F5EE' },
            { label: 'Hard',  value: score.hard,  color: '#854F0B', bg: '#FAEEDA' },
            { label: 'Again', value: score.again, color: '#A32D2D', bg: '#FCEBEB' },
          ].map(s => (
            <div key={s.label} style={{
              background: s.bg, borderRadius: '10px', padding: '12px'
            }}>
              <div style={{ fontSize: '22px', fontWeight: '600', color: s.color }}>
                {s.value}
              </div>
              <div style={{ fontSize: '12px', color: s.color }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={() => {
            setCards([])
            setDone(false)
            setScore({ good: 0, hard: 0, again: 0 })
          }}
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
          Practice Again
        </button>

      </div>
    )
  }

  // ── MAIN CARD VIEW ───────────────────────────────────────────
  return (
    <div style={{ padding: '16px' }}>

      {/* Progress indicator */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: '8px'
      }}>
        <span style={{ fontSize: '13px', color: '#666' }}>
          {currentIndex + 1} of {cards.length}
        </span>
        <span style={{ fontSize: '13px', color: '#666' }}>
          {topic}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{
        height: '4px', background: '#e0e0e0',
        borderRadius: '2px', marginBottom: '20px'
      }}>
        <div style={{
          height:       '4px',
          borderRadius: '2px',
          background:   '#500000',
          width:        `${((currentIndex + 1) / cards.length) * 100}%`,
          transition:   'width 0.3s ease'
        }} />
      </div>

      {/* Flashcard */}
      <div
        onClick={() => setFlipped(!flipped)}
        style={{
          background:    '#fff',
          border:        '1px solid #e0e0e0',
          borderRadius:  '16px',
          padding:       '40px 24px',
          textAlign:     'center',
          minHeight:     '200px',
          display:       'flex',
          flexDirection: 'column',
          alignItems:    'center',
          justifyContent: 'center',
          cursor:        'pointer',
          marginBottom:  '16px',
          transition:    'background 0.2s'
        }}
      >
        {!flipped ? (
          <>
            <p style={{ fontSize: '28px', fontWeight: '600', color: '#333', marginBottom: '8px' }}>
              {card.word}
            </p>
            <p style={{ fontSize: '13px', color: '#999' }}>
              Tap to see translation
            </p>
          </>
        ) : (
          <>
            <p style={{ fontSize: '13px', color: '#500000', fontWeight: '500', marginBottom: '6px' }}>
              TRANSLATION
            </p>
            <p style={{ fontSize: '22px', fontWeight: '600', color: '#333', marginBottom: '16px' }}>
              {card.translation}
            </p>
            {card.example && (
              <>
                <div style={{
                  height: '1px', background: '#e0e0e0',
                  width: '60%', marginBottom: '12px'
                }} />
                <p style={{ fontSize: '13px', color: '#666', fontStyle: 'italic', lineHeight: '1.5' }}>
                  "{card.example}"
                </p>
              </>
            )}
          </>
        )}
      </div>

      {/* Rating buttons */}
      {flipped && (
        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { label: 'Again', rating: 'again', color: '#A32D2D', bg: '#FCEBEB', border: '#F09595', hint: "Didn't know it" },
            { label: 'Hard',  rating: 'hard',  color: '#854F0B', bg: '#FAEEDA', border: '#FAC775', hint: 'Struggled'      },
            { label: 'Good',  rating: 'good',  color: '#0F6E56', bg: '#E1F5EE', border: '#5DCAA5', hint: 'Knew it!'       },
          ].map(btn => (
            <button
              key={btn.rating}
              onClick={() => rateCard(btn.rating)}
              style={{
                flex:         1,
                padding:      '12px 6px',
                background:   btn.bg,
                border:       `1px solid ${btn.border}`,
                borderRadius: '12px',
                color:        btn.color,
                fontSize:     '13px',
                fontWeight:   '500',
                cursor:       'pointer'
              }}
            >
              <div>{btn.label}</div>
              <div style={{ fontSize: '11px', fontWeight: '400', marginTop: '2px' }}>
                {btn.hint}
              </div>
            </button>
          ))}
        </div>
      )}

    </div>
  )
}

export default FlashcardScreen