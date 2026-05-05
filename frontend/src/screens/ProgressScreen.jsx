import { useState, useEffect } from 'react'
import axios from 'axios'

const API = 'http://127.0.0.1:8000/api'

function ProgressScreen({ level }) {
  const [progress, setProgress] = useState({
    level:         level,
    streak:        0,
    words_learned: 0,
    accuracy:      0,
  })
  const [loading, setLoading]     = useState(true)
  const [activities, setActivities] = useState([])

  const cefrLevels = ['A1', 'A2', 'B1', 'B2']
  const levelIndex = cefrLevels.indexOf(progress.level)

  useEffect(() => {
    loadProgress()
    updateStreak()
    markTodayPracticed()
    // Read activities fresh every time this screen opens
    setActivities(JSON.parse(localStorage.getItem('activities') || '[]'))
  }, [])

  useEffect(() => {
    setProgress(prev => ({ ...prev, level }))
    axios.post(`${API}/progress/`, {
      session_id: 'user_001',
      level:      level
    }).catch(e => console.error('Level save error:', e))
  }, [level])

  async function loadProgress() {
    try {
      const response = await axios.get(
        `${API}/progress/get/?session_id=user_001`
      )
      setProgress(response.data)
    } catch (error) {
      console.error('Error loading progress:', error)
    } finally {
      setLoading(false)
    }
  }

  async function updateStreak() {
    const today     = new Date().toDateString()
    const lastVisit = localStorage.getItem('lastVisit')
    const streak    = parseInt(localStorage.getItem('streak') || '0')

    if (lastVisit === today) return

    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    const newStreak = lastVisit === yesterday.toDateString()
      ? streak + 1
      : 1

    localStorage.setItem('lastVisit', today)
    localStorage.setItem('streak', newStreak.toString())

    try {
      await axios.post(`${API}/progress/`, {
        session_id: 'user_001',
        streak:     newStreak,
        level:      level
      })
      setProgress(prev => ({ ...prev, streak: newStreak }))
    } catch (e) {
      console.error('Streak save error:', e)
    }
  }

  function markTodayPracticed() {
    const today     = new Date().toDateString()
    const practiced = JSON.parse(localStorage.getItem('practicedDays') || '[]')
    if (!practiced.includes(today)) {
      practiced.push(today)
      localStorage.setItem('practicedDays', JSON.stringify(practiced))
    }
  }

  function getWeekDays() {
    const days       = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    const today      = new Date()
    const dayOfWeek  = today.getDay()
    const practiced  = JSON.parse(localStorage.getItem('practicedDays') || '[]')

    return days.map((day, i) => {
      const date         = new Date()
      const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek
      date.setDate(today.getDate() + mondayOffset + i)
      const dateStr     = date.toDateString()
      const isPracticed = practiced.includes(dateStr)
      const isToday     = dateStr === today.toDateString()
      const isFuture    = date > today
      return { day, isPracticed: isPracticed || isToday, isFuture }
    })
  }

  function formatTime(isoString) {
    const date      = new Date(isoString)
    const now       = new Date()
    const today     = now.toDateString()
    const yesterday = new Date(now - 86400000).toDateString()

    if (date.toDateString() === today) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } else if (date.toDateString() === yesterday) {
      return 'Yesterday'
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
  }

  const weekDays = getWeekDays()

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#999' }}>
        <p>Cargando progreso...</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '20px' }}>

      {/* Title */}
      <div style={{ marginBottom: '20px' }}>
        <p style={{ fontSize: '20px', fontWeight: '600', color: '#333' }}>
          Tu progreso
        </p>
        <p style={{ fontSize: '13px', color: '#888', marginTop: '2px' }}>
          Keep practicing every day!
        </p>
      </div>

      {/* 4 stat cards */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        gap: '12px', marginBottom: '20px'
      }}>
        {[
          { label: 'Day streak',    value: progress.streak,                          unit: 'days',    bg: '#FAEEDA', color: '#854F0B' },
          { label: 'Words learned', value: progress.words_learned,                   unit: 'words',   bg: '#E1F5EE', color: '#085041' },
          { label: 'Quiz accuracy', value: `${Math.round(progress.accuracy || 0)}%`, unit: 'correct', bg: '#f5f0f0', color: '#3C0000' },
          { label: 'Current level', value: progress.level || level,                  unit: 'CEFR',    bg: '#E6F1FB', color: '#0C447C' },
        ].map(stat => (
          <div key={stat.label} style={{
            background: stat.bg, borderRadius: '14px', padding: '16px'
          }}>
            <p style={{ fontSize: '12px', color: stat.color, marginBottom: '6px', opacity: 0.8 }}>
              {stat.label}
            </p>
            <p style={{ fontSize: '26px', fontWeight: '700', color: stat.color, lineHeight: 1 }}>
              {stat.value}
            </p>
            <p style={{ fontSize: '11px', color: stat.color, marginTop: '4px', opacity: 0.7 }}>
              {stat.unit}
            </p>
          </div>
        ))}
      </div>

      {/* CEFR level bar */}
      <div style={{
        background: '#fff', border: '1px solid #e0e0e0',
        borderRadius: '14px', padding: '16px', marginBottom: '16px'
      }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', marginBottom: '16px'
        }}>
          <p style={{ fontSize: '14px', fontWeight: '500', color: '#333' }}>
            CEFR Level
          </p>
          <span style={{
            background: '#f5f0f0', color: '#500000',
            borderRadius: '20px', padding: '3px 10px',
            fontSize: '12px', fontWeight: '500'
          }}>
            {progress.level || level}
          </span>
        </div>

        <div style={{ position: 'relative', marginBottom: '24px' }}>
          <div style={{
            position: 'absolute', top: '7px', left: '7px', right: '7px',
            height: '3px', background: '#e0e0e0', borderRadius: '2px'
          }}>
            <div style={{
              height: '3px', borderRadius: '2px', background: '#500000',
              width: levelIndex >= 0
                ? `${(levelIndex / (cefrLevels.length - 1)) * 100}%`
                : '0%',
              transition: 'width 0.5s ease'
            }} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}>
            {cefrLevels.map((l, i) => (
              <div key={l} style={{
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', gap: '6px'
              }}>
                <div style={{
                  width:        i <= levelIndex ? '16px' : '12px',
                  height:       i <= levelIndex ? '16px' : '12px',
                  borderRadius: '50%',
                  background:   i <= levelIndex ? '#500000' : '#e0e0e0',
                  transition:   'all 0.3s',
                  zIndex:       1
                }} />
                <span style={{
                  fontSize:   '11px',
                  color:      i <= levelIndex ? '#500000' : '#bbb',
                  fontWeight: i === levelIndex ? '700' : '400'
                }}>
                  {l}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p style={{ fontSize: '12px', color: '#888' }}>
          {levelIndex < cefrLevels.length - 1
            ? `Keep practicing to reach ${cefrLevels[levelIndex + 1]}!`
            : '¡Felicidades! You have reached the highest level!'
          }
        </p>
      </div>

      {/* This week calendar */}
      <div style={{
        background: '#fff', border: '1px solid #e0e0e0',
        borderRadius: '14px', padding: '16px', marginBottom: '16px'
      }}>
        <p style={{ fontSize: '14px', fontWeight: '500', color: '#333', marginBottom: '14px' }}>
          This week
        </p>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          {weekDays.map(({ day, isPracticed, isFuture }) => (
            <div key={day} style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', gap: '6px'
            }}>
              <div style={{
                width:          '36px',
                height:         '36px',
                borderRadius:   '10px',
                background:     isFuture ? '#f5f5f5' : isPracticed ? '#500000' : '#f0f0f0',
                display:        'flex',
                alignItems:     'center',
                justifyContent: 'center'
              }}>
                {!isFuture && isPracticed && (
                  <span style={{ color: '#fff', fontSize: '16px' }}>✓</span>
                )}
              </div>
              <span style={{ fontSize: '11px', color: '#999' }}>{day}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent activity */}
      <div style={{
        background: '#fff', border: '1px solid #e0e0e0',
        borderRadius: '14px', padding: '16px'
      }}>
        <p style={{ fontSize: '14px', fontWeight: '500', color: '#333', marginBottom: '12px' }}>
          Recent activity
        </p>

        {activities.length === 0 ? (
          <p style={{ fontSize: '13px', color: '#999', textAlign: 'center', padding: '12px 0' }}>
            No activity yet — start chatting, practicing flashcards, or taking a quiz!
          </p>
        ) : (
          activities.slice(0, 5).map((activity, i, arr) => (
            <div key={i} style={{
              display:        'flex',
              alignItems:     'center',
              justifyContent: 'space-between',
              paddingBottom:  i < arr.length - 1 ? '12px' : '0',
              marginBottom:   i < arr.length - 1 ? '12px' : '0',
              borderBottom:   i < arr.length - 1 ? '1px solid #f0f0f0' : 'none'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width:        '10px',
                  height:       '10px',
                  borderRadius: '50%',
                  background:   activity.color,
                  flexShrink:   0
                }} />
                <span style={{ fontSize: '13px', color: '#333' }}>
                  {activity.label}
                </span>
              </div>
              <span style={{ fontSize: '12px', color: '#999' }}>
                {formatTime(activity.time)}
              </span>
            </div>
          ))
        )}
      </div>

    </div>
  )
}

export default ProgressScreen