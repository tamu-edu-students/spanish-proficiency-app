import { useState, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

const GREETING = {
  'A1': '¡Hola! (Hello!) Soy tu tutor. (I am your tutor.) ¿Como te llamas? (What is your name?)',
  'A2': '¡Hola! Soy tu tutor de español. ¿Cómo estás hoy?',
  'B1': '¡Hola! Soy tu tutor de español. ¿De qué quieres hablar hoy?',
  'B2': '¡Bienvenido! Soy tu tutor de español. ¿Sobre qué tema te gustaría conversar hoy?',
}

function ChatScreen({ level, sessionId }) {
  const [messages, setMessages] = useState([
    { role: 'model', parts: [GREETING[level] || GREETING['B1']] }
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)

  // Reset conversation when level changes
  useEffect(() => {
    setMessages([
      { role: 'model', parts: [GREETING[level] || GREETING['B1']] }
    ])
    setInput('')
  }, [level])

  async function sendMessage() {
    if (!input.trim()) return

    const userMessage     = { role: 'user', parts: [input] }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setLoading(true)

    try {
      const activities     = JSON.parse(localStorage.getItem('activities') || '[]')
      const lastActivity   = activities[0]
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
      const recentChat     = lastActivity &&
        lastActivity.label === 'Chat conversation' &&
        new Date(lastActivity.time) > fiveMinutesAgo

      if (!recentChat) {
        activities.unshift({
          label: 'Chat conversation',
          color: '#500000',
          time:  new Date().toISOString()
        })
        localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))
      }
    } catch (e) {
      console.error('Activity tracking error:', e)
    }

    try {
      const response = await axios.post(`${API}/chat/`, {
        messages:   updatedMessages,
        level:      level,
        session_id: sessionId
      })

      setMessages([...updatedMessages, {
        role:  'model',
        parts: [response.data.reply]
      }])

    } catch (error) {
      console.error('Error:', error)
      setMessages([...updatedMessages, {
        role:  'model',
        parts: ['Lo siento, hubo un error. Por favor intenta de nuevo.']
      }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Level indicator */}
      <div style={{
        padding:    '8px 16px',
        background: '#faf8f8',
        borderBottom: '1px solid #f0e8e8',
        fontSize:   '12px',
        color:      '#888',
        fontFamily: "'Open Sans', sans-serif"
      }}>
        Chatting at level <strong style={{ color: '#500000' }}>{level}</strong> — change level in sidebar to restart conversation
      </div>

      {/* Message list */}
      <div style={{
        flex:          1,
        overflowY:     'auto',
        padding:       '16px',
        display:       'flex',
        flexDirection: 'column',
        gap:           '12px'
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display:        'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
          }}>
            <div style={{
              maxWidth:     '80%',
              padding:      '10px 14px',
              borderRadius: msg.role === 'user'
                ? '16px 16px 4px 16px'
                : '16px 16px 16px 4px',
              background: msg.role === 'user' ? '#500000' : '#fff',
              color:      msg.role === 'user' ? '#fff'    : '#333',
              fontSize:   '14px',
              lineHeight: '1.5',
              border:     msg.role === 'model' ? '1px solid #e0e0e0' : 'none'
            }}>
              {msg.parts[0]}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{
              padding:      '10px 14px',
              borderRadius: '16px 16px 16px 4px',
              background:   '#fff',
              border:       '1px solid #e0e0e0',
              fontSize:     '14px',
              color:        '#888'
            }}>
              Escribiendo...
            </div>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div style={{
        padding:    '12px 16px',
        borderTop:  '1px solid #e0e0e0',
        background: '#fff',
        display:    'flex',
        gap:        '8px'
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe en español..."
          style={{
            flex:         1,
            padding:      '10px 14px',
            border:       '1px solid #e0e0e0',
            borderRadius: '20px',
            fontSize:     '14px',
            outline:      'none'
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading}
          style={{
            width:        '40px',
            height:       '40px',
            borderRadius: '50%',
            background:   loading ? '#ccc' : '#500000',
            border:       'none',
            cursor:       loading ? 'not-allowed' : 'pointer',
            color:        'white',
            fontSize:     '16px'
          }}
        >
          →
        </button>
      </div>

    </div>
  )
}

export default ChatScreen