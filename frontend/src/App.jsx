import { useState, useEffect } from 'react'
import axios from 'axios'
import ChatScreen      from './screens/ChatScreen'
import FlashcardScreen from './screens/FlashcardScreen'
import QuizScreen      from './screens/QuizScreen'
import ProgressScreen  from './screens/ProgressScreen'
import VoiceScreen     from './screens/VoiceScreen'
import './App.css'

const API = 'http://127.0.0.1:8000/api'

const LEVELS = [
  { value: 'A1', label: 'A1 — Beginner'          },
  { value: 'A2', label: 'A2 — Elementary'         },
  { value: 'B1', label: 'B1 — Intermediate'       },
  { value: 'B2', label: 'B2 — Upper Intermediate' },
]

const TABS = [
  { key: 'chat',      label: '💬 Chat'     },
  { key: 'flashcard', label: '🃏 Tarjetas' },
  { key: 'quiz',      label: '📝 Quiz'     },
  { key: 'progress',  label: '📊 Progreso' },
  { key: 'voice',     label: '🎤 Voz'      },
]

function LevelSelect({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="level-select"
    >
      {LEVELS.map(l => (
        <option key={l.value} value={l.value}>{l.label}</option>
      ))}
    </select>
  )
}

function App() {
  const [activeTab, setActiveTab] = useState('chat')
  const [userLevel, setUserLevel] = useState('B1')

  // ── Update streak every time app opens ──────────────────────
  // Words learned and quiz accuracy NEVER reset — only streak resets
  // if user misses a day
  useEffect(() => {
    updateStreak()
    markTodayPracticed()
  }, [])

  function updateStreak() {
    const today     = new Date().toDateString()
    const lastVisit = localStorage.getItem('lastVisit')
    const streak    = parseInt(localStorage.getItem('streak') || '0')

    // Already counted today — don't update
    if (lastVisit === today) return

    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)

    // If practiced yesterday → continue streak
    // If missed a day → reset streak to 1
    // Words learned and accuracy are NOT touched here — they persist forever
    const newStreak = lastVisit === yesterday.toDateString()
      ? streak + 1
      : 1

    localStorage.setItem('lastVisit', today)
    localStorage.setItem('streak', newStreak.toString())

    // Save only streak to backend — words and accuracy unchanged
    axios.post(`${API}/progress/`, {
      session_id: 'user_001',
      streak:     newStreak
    }).catch(e => console.error('Streak save error:', e))
  }

  function markTodayPracticed() {
    const today     = new Date().toDateString()
    const practiced = JSON.parse(localStorage.getItem('practicedDays') || '[]')
    if (!practiced.includes(today)) {
      practiced.push(today)
      localStorage.setItem('practicedDays', JSON.stringify(practiced))
    }
  }

  return (
    <div className="app">

      {/* Mobile header */}
      <div className="header">
        <span className="app-title">EspañolAI</span>
        <LevelSelect value={userLevel} onChange={setUserLevel} />
      </div>

      {/* Sidebar (desktop) / Tab bar (mobile) */}
      <div className="tab-bar">
        <div className="sidebar-title">EspañolAI</div>
        <div className="sidebar-level">
          <LevelSelect value={userLevel} onChange={setUserLevel} />
        </div>
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="screen-area">
        {activeTab === 'chat'      && <ChatScreen      level={userLevel} />}
        {activeTab === 'flashcard' && <FlashcardScreen level={userLevel} />}
        {activeTab === 'quiz'      && <QuizScreen      level={userLevel} />}
        {activeTab === 'progress'  && <ProgressScreen  level={userLevel} key={activeTab} />}
        {activeTab === 'voice'     && <VoiceScreen     level={userLevel} />}
      </div>

    </div>
  )
}

export default App