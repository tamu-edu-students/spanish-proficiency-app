import { useState, useEffect } from 'react'
import axios from 'axios'
import ChatScreen      from './screens/ChatScreen'
import FlashcardScreen from './screens/FlashcardScreen'
import QuizScreen      from './screens/QuizScreen'
import ProgressScreen  from './screens/ProgressScreen'
import VoiceScreen     from './screens/VoiceScreen'
import GradingScreen   from './screens/GradingScreen'
import './App.css'

const API = '/api'

const LEVELS = [
  { value: 'A1', label: 'A1 - Beginner'          },
  { value: 'A2', label: 'A2 - Elementary'         },
  { value: 'B1', label: 'B1 - Intermediate'       },
  { value: 'B2', label: 'B2 - Upper Intermediate' },
]

const TAB_LABELS = {
  en: {
    chat: 'Chat',
    flashcard: 'Cards',
    quiz: 'Grammar Quiz',
    reading: 'Reading Comprehension',
    writing: 'Graded Writing',
    speaking: 'Graded Speaking',
    progress: 'Progress',
    voice: 'Voice',
  },
  es: {
    chat: 'Chat',
    flashcard: 'Tarjetas',
    quiz: 'Prueba de gramática',
    reading: 'Comprensión lectora',
    writing: 'Escritura calificada',
    speaking: 'Expresión oral calificada',
    progress: 'Progreso',
    voice: 'Voz',
  },
}

const LANGUAGE_TOGGLE_LABELS = {
  en: 'English',
  es: 'Español',
}

function LevelSelect({ value, onChange, disabled }) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="level-select"
        style={{ opacity: disabled ? 0.45 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
      >
        {LEVELS.map(l => (
          <option key={l.value} value={l.value}>{l.label}</option>
        ))}
      </select>
      {disabled && (
        <div style={{
          position:   'absolute',
          bottom:     '-18px',
          left:       '0',
          fontSize:   '10px',
          color:      '#999',
          whiteSpace: 'nowrap',
          fontFamily: "'Open Sans', sans-serif"
        }}>
          Change level before Voice
        </div>
      )}
    </div>
  )
}

function App() {
  const [activeTab, setActiveTab]       = useState('chat')
  const [userLevel, setUserLevel]       = useState('A1')
  const [user, setUser]                 = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [labelLanguage, setLabelLanguage] = useState('en')

  const levelLocked = activeTab === 'voice'
  const tabLabels = TAB_LABELS[labelLanguage] || TAB_LABELS.en

  useEffect(() => {
    checkAuth()
  }, [])

  useEffect(() => {
    if (user) {
      updateStreak()
      markTodayPracticed()
    }
  }, [user])

  async function checkAuth() {
    try {
      const response = await axios.get(`${API}/me/`, { withCredentials: true })
      setUser(response.data)
    } catch {
      setUser(null)
    } finally {
      setCheckingAuth(false)
    }
  }

  function login() {
    window.location.href = '/accounts/login/?next=/'
  }

  function logout() {
    window.location.href = '/accounts/logout/'
  }

  function updateStreak() {
    const today     = new Date().toDateString()
    const lastVisit = localStorage.getItem('lastVisit')
    const streak    = parseInt(localStorage.getItem('streak') || '0')

    if (lastVisit === today) return

    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)

    const newStreak = lastVisit === yesterday.toDateString() ? streak + 1 : 1

    localStorage.setItem('lastVisit', today)
    localStorage.setItem('streak', newStreak.toString())

    axios.post(`${API}/progress/`, {
      session_id: user?.session_id || 'dev_001',
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

  // Loading screen
  if (checkingAuth) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#500000' }}>
        <div style={{ textAlign: 'center' }}>
          <img
            src="https://aux.tamu.edu/logos/boxTAM.svg"
            alt="Texas A&M"
            style={{ height: '60px', display: 'block', margin: '0 auto 20px', filter: 'brightness(0) invert(1)' }}
          />
          <p style={{ fontFamily: "'Oswald', sans-serif", fontSize: '16px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.8)' }}>
            Loading EspañolAI...
          </p>
        </div>
      </div>
    )
  }

  // Login screen
  if (!user) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#500000' }}>
        <div style={{ background: 'white', padding: '48px 40px', textAlign: 'center', maxWidth: '400px', width: '90%', borderTop: '6px solid #3C0000' }}>
          <img
            src="https://aux.tamu.edu/logos/boxTAM.svg"
            alt="Texas A&M University"
            style={{ height: '50px', marginBottom: '12px' }}
          />
          <p style={{ fontFamily: "'Oswald', sans-serif", fontSize: '26px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#500000', marginBottom: '8px' }}>
            EspañolAI
          </p>
          <p style={{ fontFamily: "'Open Sans', sans-serif", fontSize: '13px', color: '#707070', marginBottom: '32px', lineHeight: '1.6' }}>
            AI-powered Spanish tutor for Texas A&M students. Sign in with your TAMU NetID to get started.
          </p>
          <button
            onClick={login}
            style={{ width: '100%', padding: '14px', background: '#500000', color: 'white', border: 'none', fontSize: '14px', fontFamily: "'Oswald', sans-serif", fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer', marginBottom: '16px' }}
            onMouseEnter={e => e.target.style.background = '#3C0000'}
            onMouseLeave={e => e.target.style.background = '#500000'}
          >
            Sign in with TAMU NetID
          </button>
          <p style={{ fontFamily: "'Open Sans', sans-serif", fontSize: '11px', color: '#999' }}>
            Uses Texas A&M Central Authentication Service (CAS)
          </p>
        </div>
      </div>
    )
  }

  const SESSION_ID = user.session_id

  return (
    <div className="app">

      {/* Mobile header */}
      <div className="header">
        <span className="app-title">EspañolAI</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingBottom: levelLocked ? '12px' : '0' }}>
          <LevelSelect value={userLevel} onChange={setUserLevel} disabled={levelLocked} />
          {!user.dev_mode && (
            <button
              onClick={logout}
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white', border: '1px solid rgba(255,255,255,0.3)', padding: '4px 10px', fontSize: '11px', fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.06em', cursor: 'pointer' }}
            >
              Sign Out
            </button>
          )}
        </div>
      </div>

      {/* Sidebar on desktop / bottom tab bar on mobile */}
      <div className="tab-bar">

        <div className="sidebar-logo">
          <img src="https://aux.tamu.edu/logos/boxTAM.svg" alt="Texas A&M University" />
        </div>

        <div className="sidebar-title">EspañolAI</div>

        <div className="sidebar-language">
          <span className="sidebar-level-label">Labels</span>
          <div className="language-toggle">
            <button
              type="button"
              className={labelLanguage === 'en' ? 'language-toggle-btn active' : 'language-toggle-btn'}
              onClick={() => setLabelLanguage('en')}
            >
              English
            </button>
            <button
              type="button"
              className={labelLanguage === 'es' ? 'language-toggle-btn active' : 'language-toggle-btn'}
              onClick={() => setLabelLanguage('es')}
            >
              Español
            </button>
          </div>
        </div>

        {/* User info - desktop only */}
        <div className="sidebar-user">
          {user.dev_mode ? (
            <div>
              <span className="dev-badge">Dev Mode</span>
              <p className="user-name">{user.name || user.netid}</p>
            </div>
          ) : (
            <div>
              <p className="user-name">{user.name || user.netid}</p>
              <p className="user-email">{user.netid}@tamu.edu</p>
              <button className="signout-btn" onClick={logout}>Sign Out</button>
            </div>
          )}
        </div>

        {/* Level selector - locked on Voz tab */}
        <div className="sidebar-level">
          <span className="sidebar-level-label">
            Proficiency Level {levelLocked ? '(locked on Voz)' : ''}
          </span>
          <LevelSelect value={userLevel} onChange={setUserLevel} disabled={levelLocked} />
        </div>

        {Object.keys(tabLabels).map(tabKey => (
          <button
            key={tabKey}
            className={`tab-btn ${activeTab === tabKey ? 'active' : ''}`}
            onClick={() => setActiveTab(tabKey)}
          >
            {tabLabels[tabKey]}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="screen-area">
        {activeTab === 'chat'      && <ChatScreen      level={userLevel} sessionId={SESSION_ID} />}
        {activeTab === 'flashcard' && <FlashcardScreen level={userLevel} sessionId={SESSION_ID} />}
        {activeTab === 'quiz'      && <QuizScreen      level={userLevel} sessionId={SESSION_ID} quizType="grammar" />}
        {activeTab === 'reading'  && <QuizScreen      level={userLevel} sessionId={SESSION_ID} quizType="reading" />}
        {activeTab === 'writing'   && <GradingScreen   kind="essay" level={userLevel} sessionId={SESSION_ID} />}
        {activeTab === 'speaking'  && <GradingScreen   kind="audio" level={userLevel} sessionId={SESSION_ID} />}
        {activeTab === 'progress'  && <ProgressScreen  level={userLevel} sessionId={SESSION_ID} />}
        {activeTab === 'voice'     && <VoiceScreen     level={userLevel} />}
      </div>

    </div>
  )
}

export default App