import { useState, useEffect } from 'react'
import axios from 'axios'
import { TOPICS } from '../topics'

const API = '/api'

// Topic-aware opening line per CEFR level — the model itself is steered toward
// the topic via the system prompt (see gemini_service.build_system_prompt),
// this greeting just announces it in a level-appropriate way.
const TOPIC_GREETING = {
  'A1': topic => `¡Hola! (Hello!) Vamos a hablar de ${topic}. (Let's talk about ${topic}.) ¿Qué sabes de este tema? (What do you know about this topic?)`,
  'A2': topic => `¡Hola! Hoy vamos a hablar sobre ${topic}. ¿Qué sabes de este tema?`,
  'B1': topic => `¡Hola! Soy tu tutor de español. Vamos a conversar sobre ${topic}. ¿Qué te gustaría compartir sobre este tema?`,
  'B2': topic => `¡Bienvenido! Soy tu tutor de español. Conversemos sobre ${topic}. ¿Cuál es tu experiencia o perspectiva sobre este tema?`,
}

function ChatScreen({ level, sessionId }) {
  const [topic, setTopic]         = useState(null)
  const [topicDraft, setTopicDraft] = useState('')
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)

  // Reset the conversation (and topic choice) when level changes
  useEffect(() => {
    setTopic(null)
    setMessages([])
    setInput('')
  }, [level])

  function startChat(chosenTopic) {
    const picked = chosenTopic.trim()
    if (!picked) return
    setTopic(picked)
    const greet = TOPIC_GREETING[level] || TOPIC_GREETING['B1']
    setMessages([{ role: 'model', parts: [greet(picked)] }])
  }

  function changeTopic() {
    setTopic(null)
    setMessages([])
    setInput('')
  }

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
        session_id: sessionId,
        topic:      topic
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

  // TOPIC PICKER — shown before the conversation starts, same pattern as Cards.
  if (!topic) {
    return (
      <div style={{ padding: '20px' }}>

        <p style={{ fontSize: '15px', color: '#666', marginBottom: '16px', lineHeight: '1.5' }}>
          Choose a topic and start a Spanish conversation about it with your tutor.
        </p>

        <p style={{ fontSize: '15px', fontWeight: '500', marginBottom: '8px' }}>
          Choose a topic:
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '20px' }}>
          {TOPICS.map(topicOption => (
            <button
              key={topicOption}
              onClick={() => startChat(topicOption)}
              style={{
                padding:      '6px 12px',
                borderRadius: '20px',
                border:       '1px solid #e0e0e0',
                background:   '#fff',
                color:        '#666',
                fontSize:     '14px',
                cursor:       'pointer'
              }}
            >
              {topicOption}
            </button>
          ))}
        </div>

        <p style={{ fontSize: '15px', fontWeight: '500', marginBottom: '8px' }}>
          Or type your own topic:
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            value={topicDraft}
            onChange={e => setTopicDraft(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') startChat(topicDraft) }}
            placeholder="e.g. Classroom Management, IEPs..."
            style={{
              flex:         1,
              padding:      '10px 14px',
              border:       '1px solid #e0e0e0',
              borderRadius: '10px',
              fontSize:     '15px',
              outline:      'none'
            }}
          />
          <button
            onClick={() => startChat(topicDraft)}
            disabled={!topicDraft.trim()}
            style={{
              padding:      '10px 20px',
              background:   topicDraft.trim() ? '#500000' : '#ccc',
              color:        '#fff',
              border:       'none',
              borderRadius: '10px',
              fontSize:     '15px',
              fontWeight:   '500',
              cursor:       topicDraft.trim() ? 'pointer' : 'not-allowed'
            }}
          >
            Start
          </button>
        </div>

      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Level + topic indicator */}
      <div style={{
        padding:    '8px 16px',
        background: '#faf8f8',
        borderBottom: '1px solid #f0e8e8',
        fontSize:   '14px',
        color:      '#888',
        fontFamily: "'Open Sans', sans-serif",
        display:    'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap:        '12px',
        flexWrap:   'wrap'
      }}>
        <span>
          Chatting at level <strong style={{ color: '#500000' }}>{level}</strong> about <strong style={{ color: '#500000' }}>{topic}</strong>
        </span>
        <button
          onClick={changeTopic}
          style={{ background: 'none', border: 'none', color: '#500000', fontSize: '14px', cursor: 'pointer', textDecoration: 'underline', padding: 0 }}
        >
          Change topic
        </button>
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
              fontSize:   '15px',
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
              fontSize:     '15px',
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
            fontSize:     '15px',
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
            fontSize:     '17px'
          }}
        >
          →
        </button>
      </div>

    </div>
  )
}

export default ChatScreen