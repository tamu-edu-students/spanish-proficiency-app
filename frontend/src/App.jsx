import { Fragment, useState, useEffect } from 'react'
import axios from 'axios'
import ChatScreen      from './screens/ChatScreen'
import FlashcardScreen from './screens/FlashcardScreen'
import QuizScreen      from './screens/QuizScreen'
import ProgressScreen  from './screens/ProgressScreen'
import VoiceScreen     from './screens/VoiceScreen'
import GradingScreen   from './screens/GradingScreen'
import { strings }     from './i18n'
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
    voice: 'Voice',
    reading: 'Reading',
    writing: 'Writing',
    speaking: 'Graded Speaking',
    oral: 'Oral Tasks',
    chat: 'Chat',
    flashcard: 'Cards',
    quiz: 'Grammar Quiz',
    progress: 'Progress',
  },
  es: {
    voice: 'Voz',
    reading: 'Lectura',
    writing: 'Escritura',
    speaking: 'Expresión oral calificada',
    oral: 'Tareas orales',
    chat: 'Chat',
    flashcard: 'Tarjetas',
    quiz: 'Prueba de gramática',
    progress: 'Progreso',
  },
}

// Sidebar sections, in display order. Empty tabs[] renders a "coming soon" stub.
const TAB_SECTIONS = [
  { en: 'Listening', es: 'Comprensión auditiva', tabs: [] },
  { en: 'Speaking',  es: 'Expresión oral',       tabs: ['speaking', 'voice'] },
  { en: 'BTLPT Oral Exam', es: 'Examen Oral BTLPT', tabs: ['oral'] },
  { en: 'Reading',   es: 'Lectura',              tabs: ['reading'] },
  { en: 'Writing',   es: 'Escritura',            tabs: ['writing'] },
  { en: 'More',      es: 'Más',                  tabs: ['chat', 'flashcard', 'quiz', 'progress'] },
]

// Writing's BTLPT task types (Domain IV), nested under the Writing tab.
const WRITING_TYPES = ['opinion', 'correspondence', 'lesson_plan']
const WRITING_TYPE_LABEL_KEY = {
  opinion:        'taskTypeOpinion',
  correspondence: 'taskTypeLetter',
  lesson_plan:    'taskTypeLessonPlan',
}

// Oral Expression's BTLPT task types (Domain II), nested under the Oral tab,
// each mapped to its sidebar label key in i18n.js. Q&A 1 and Q&A 2 share one
// tab — same scenario, two related questions answered in a single recording.
const ORAL_TYPES = ['conversation', 'qa', 'presentation', 'situation']
const ORAL_TYPE_LABEL_KEY = {
  conversation: 'oralTypeConversation',
  qa:           'oralTypeQA',
  presentation: 'oralTypePresentation',
  situation:    'oralTypeSituation',
}

const LANGUAGE_TOGGLE_LABELS = {
  en: 'English',
  es: 'Español',
}

function LevelSelect({ value, onChange, disabled, t }) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        aria-label={t.proficiencyLevel}
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
          fontSize:   '12px',
          color:      '#666',
          whiteSpace: 'nowrap',
          fontFamily: "'Open Sans', sans-serif"
        }}>
          {t.levelLockedHint}
        </div>
      )}
    </div>
  )
}

function App() {
  const [activeTab, setActiveTab]       = useState('chat')
  const [essayType, setEssayType]       = useState('opinion')
  const [oralType, setOralType]         = useState('conversation')
  const [userLevel, setUserLevel]       = useState('A1')
  const [user, setUser]                 = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [labelLanguage, setLabelLanguage] = useState('en')

  const levelLocked = activeTab === 'voice'
  const tabLabels = TAB_LABELS[labelLanguage] || TAB_LABELS.en
  const t = strings(labelLanguage)

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
      <div role="status" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#500000' }}>
        <div style={{ textAlign: 'center' }}>
          <img
            src="https://aux.tamu.edu/logos/boxTAM.svg"
            alt="Texas A&M"
            style={{ height: '60px', display: 'block', margin: '0 auto 20px', filter: 'brightness(0) invert(1)' }}
          />
          <p style={{ fontFamily: "'Oswald', sans-serif", fontSize: '17px', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'rgba(255,255,255,0.8)' }}>
            {t.loading}
          </p>
        </div>
      </div>
    )
  }

  // Login screen
  if (!user) {
    return (
      <main style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#500000' }}>
        <div style={{ background: 'white', padding: '48px 40px', textAlign: 'center', maxWidth: '400px', width: '90%', borderTop: '6px solid #3C0000' }}>
          <img
            src="https://aux.tamu.edu/logos/boxTAM.svg"
            alt="Texas A&M University"
            style={{ height: '50px', marginBottom: '12px' }}
          />
          <h1 style={{ fontFamily: "'Oswald', sans-serif", fontSize: '26px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#500000', marginBottom: '4px' }}>
            Avanza Español
          </h1>
          <p style={{ fontFamily: "'Oswald', sans-serif", fontSize: '13px', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#a06060', marginBottom: '20px' }}>
            Spanish for Texas Teachers
          </p>
          <p style={{ fontFamily: "'Open Sans', sans-serif", fontSize: '15px', color: '#707070', marginBottom: '32px', lineHeight: '1.6' }}>
            AI-powered Spanish tutor for Texas A&M students. Sign in with your TAMU NetID to get started.
          </p>
          <button
            onClick={login}
            style={{ width: '100%', padding: '14px', background: '#500000', color: 'white', border: 'none', fontSize: '15px', fontFamily: "'Oswald', sans-serif", fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer', marginBottom: '16px' }}
            onMouseEnter={e => e.target.style.background = '#3C0000'}
            onMouseLeave={e => e.target.style.background = '#500000'}
          >
            Sign in with TAMU NetID
          </button>
          <p style={{ fontFamily: "'Open Sans', sans-serif", fontSize: '13px', color: '#666' }}>
            Uses Texas A&M Central Authentication Service (CAS)
          </p>
        </div>
      </main>
    )
  }

  const SESSION_ID = user.session_id

  return (
    <div className="app">
      <a href="#main" className="skip-link">{t.skipToContent}</a>

      {/* Mobile header */}
      <header className="header" lang={labelLanguage}>
        <div>
          <div className="app-title">Avanza Español</div>
          <div className="app-subtitle">Spanish for Texas Teachers</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingBottom: levelLocked ? '12px' : '0' }}>
          <LevelSelect value={userLevel} onChange={setUserLevel} disabled={levelLocked} t={t} />
          <button
            type="button"
            className="header-lang-btn"
            lang={labelLanguage === 'en' ? 'es' : 'en'}
            onClick={() => setLabelLanguage(labelLanguage === 'en' ? 'es' : 'en')}
          >
            {labelLanguage === 'en' ? 'Español' : 'English'}
          </button>
          {!user.dev_mode && (
            <button
              onClick={logout}
              style={{ background: 'rgba(255,255,255,0.15)', color: 'white', border: '1px solid rgba(255,255,255,0.3)', padding: '4px 10px', fontSize: '13px', fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.06em', cursor: 'pointer' }}
            >
              {t.signOut}
            </button>
          )}
        </div>
      </header>

      {/* Sidebar on desktop / bottom tab bar on mobile */}
      <nav className="tab-bar" aria-label={t.mainNavigation} lang={labelLanguage}>

        <div className="sidebar-logo">
          <img src="https://aux.tamu.edu/logos/boxTAM.svg" alt="Texas A&M University" />
        </div>

        <div className="sidebar-title">
          Avanza Español
          <div className="sidebar-subtitle">Spanish for Texas Teachers</div>
        </div>

        <div className="sidebar-language">
          <span className="sidebar-level-label">{t.labels}</span>
          <div className="language-toggle">
            <button
              type="button"
              className={labelLanguage === 'en' ? 'language-toggle-btn active' : 'language-toggle-btn'}
              aria-pressed={labelLanguage === 'en'}
              lang="en"
              onClick={() => setLabelLanguage('en')}
            >
              English
            </button>
            <button
              type="button"
              className={labelLanguage === 'es' ? 'language-toggle-btn active' : 'language-toggle-btn'}
              aria-pressed={labelLanguage === 'es'}
              lang="es"
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
              <span className="dev-badge">{t.devMode}</span>
              <p className="user-name">{user.name || user.netid}</p>
            </div>
          ) : (
            <div>
              <p className="user-name">{user.name || user.netid}</p>
              <p className="user-email">{user.netid}@tamu.edu</p>
              <button className="signout-btn" onClick={logout}>{t.signOut}</button>
            </div>
          )}
        </div>

        {/* Level selector - locked on Voz tab */}
        <div className="sidebar-level">
          <span className="sidebar-level-label">
            {t.proficiencyLevel} {levelLocked ? t.lockedOnVoice : ''}
          </span>
          <LevelSelect value={userLevel} onChange={setUserLevel} disabled={levelLocked} t={t} />
        </div>

        {TAB_SECTIONS.map(section => (
          <div className="tab-section" key={section.en}>
            <span className="tab-section-label">{section[labelLanguage] || section.en}</span>
            {section.tabs.length === 0 ? (
              <button className="tab-btn" disabled>{(section[labelLanguage] || section.en) + ' — ' + t.comingSoon}</button>
            ) : section.tabs.map(tabKey => (
              <Fragment key={tabKey}>
                <button
                  className={`tab-btn ${activeTab === tabKey ? 'active' : ''}`}
                  aria-current={activeTab === tabKey ? 'page' : undefined}
                  onClick={() => setActiveTab(tabKey)}
                >
                  {tabLabels[tabKey]}
                </button>
                {tabKey === 'writing' && activeTab === 'writing' && WRITING_TYPES.map(type => (
                  <button
                    key={type}
                    className={`tab-btn tab-subitem ${essayType === type ? 'active' : ''}`}
                    aria-current={essayType === type ? 'true' : undefined}
                    onClick={() => setEssayType(type)}
                  >
                    {t[WRITING_TYPE_LABEL_KEY[type]]}
                  </button>
                ))}
                {tabKey === 'oral' && activeTab === 'oral' && ORAL_TYPES.map(type => (
                  <button
                    key={type}
                    className={`tab-btn tab-subitem ${oralType === type ? 'active' : ''}`}
                    aria-current={oralType === type ? 'true' : undefined}
                    onClick={() => setOralType(type)}
                  >
                    {t[ORAL_TYPE_LABEL_KEY[type]]}
                  </button>
                ))}
              </Fragment>
            ))}
          </div>
        ))}

      </nav>

      {/* Main content */}
      <main id="main" className="screen-area" tabIndex={0}>
        <h1 className="sr-only">{`Avanza Español: ${tabLabels[activeTab]}`}</h1>
        {activeTab === 'chat'      && <ChatScreen      level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'flashcard' && <FlashcardScreen level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'quiz'      && <QuizScreen      level={userLevel} sessionId={SESSION_ID} quizType="grammar" lang={labelLanguage} />}
        {activeTab === 'reading'  && <QuizScreen      level={userLevel} sessionId={SESSION_ID} quizType="reading" lang={labelLanguage} />}
        {/* key={essayType}/{oralType} forces a full remount on subsection switch — otherwise
            the same EssayTab/AudioTab instance stays mounted and carries over its draft
            text/recording from the previous task type. */}
        {activeTab === 'writing'   && <GradingScreen   key={essayType} kind="essay" essayType={essayType} level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'speaking'  && <GradingScreen   kind="audio" level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'oral'      && <GradingScreen   key={oralType} kind="audio" oralType={oralType} level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'progress'  && <ProgressScreen  level={userLevel} sessionId={SESSION_ID} lang={labelLanguage} />}
        {activeTab === 'voice'     && <VoiceScreen     level={userLevel} lang={labelLanguage} />}
      </main>

    </div>
  )
}

export default App