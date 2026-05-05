import { useState } from 'react'
import axios from 'axios'

const API = 'http://127.0.0.1:8000/api'

function ChatScreen({ level }) {
  const [messages, setMessages] = useState([
    {
      role: 'model',
      parts: ['¡Hola! Soy tu tutor de español. ¿De qué quieres hablar hoy?']
    }
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)

  async function sendMessage() {
    if (!input.trim()) return

    const userMessage     = { role: 'user', parts: [input] }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setLoading(true)

    // ── Track activity BEFORE API call so it always saves ──
    try {
      const activities = JSON.parse(localStorage.getItem('activities') || '[]')
      activities.unshift({
        label: 'Chat conversation',
        color: '#500000',
        time:  new Date().toISOString()
      })
      localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))
    } catch (e) {
      console.error('Activity tracking error:', e)
    }

    try {
      const response = await axios.post(`${API}/chat/`, {
        messages:   updatedMessages,
        level:      level,
        session_id: 'user_001'
      })

      const botMessage = {
        role:  'model',
        parts: [response.data.reply]
      }
      setMessages([...updatedMessages, botMessage])

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

      {/* Message list */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px',
        display: 'flex', flexDirection: 'column', gap: '12px'
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

        {/* Typing indicator */}
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