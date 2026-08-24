import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const API = '/api'

function VoiceScreen({ level }) {
  const [status, setStatus]         = useState('Tap the mic to start')
  const [listening, setListening]   = useState(false)
  const [speaking, setSpeaking]     = useState(false)
  const [thinking, setThinking]     = useState(false)
  const [transcript, setTranscript] = useState('')
  const [liveText, setLiveText]     = useState('')
  const [reply, setReply]           = useState('')
  const [history, setHistory]       = useState([])

  const recognitionRef = useRef(null)
  const levelRef       = useRef(level)
  const listeningRef   = useRef(false)
  const accumulatedRef = useRef('')
  const historyRef     = useRef([])

  // Keep levelRef and historyRef always in sync
  useEffect(() => {
    levelRef.current = level
  }, [level])

  useEffect(() => {
    historyRef.current = history
  }, [history])

  function trackVoiceActivity() {
    try {
      const activities     = JSON.parse(localStorage.getItem('activities') || '[]')
      const lastActivity   = activities[0]
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000)
      const recentVoice    = lastActivity &&
        lastActivity.label === 'Voice conversation' &&
        new Date(lastActivity.time) > fiveMinutesAgo
      if (!recentVoice) {
        activities.unshift({
          label: 'Voice conversation',
          color: '#E24B4A',
          time:  new Date().toISOString()
        })
        localStorage.setItem('activities', JSON.stringify(activities.slice(0, 10)))
      }
    } catch {
      return
    }
  }

  // Strip bracketed English text before speaking
  // e.g. "Hola (hello), como estas (how are you)?" -> "Hola, como estas?"
  function stripBrackets(text) {
    return text
      .replace(/\(.*?\)/g, '')   // remove (anything in parens)
      .replace(/\s{2,}/g, ' ')   // collapse double spaces
      .replace(/\s,/g, ',')      // fix " ," -> ","
      .replace(/\s\./g, '.')     // fix " ." -> "."
      .trim()
  }

  async function sendToGemini(userText) {
    setThinking(true)
    setStatus('Gemini esta pensando...')

    // Read from refs so we always have current values, not stale closure
    const currentLevel   = levelRef.current
    const currentHistory = historyRef.current

    try {
      const newMessages = [
        ...currentHistory,
        { role: 'user', parts: [userText] }
      ]

      const response = await axios.post(`${API}/chat/`, {
        messages:   newMessages,
        level:      currentLevel,
        session_id: 'voice_user'
      })

      const spanishReply = response.data.reply
      setReply(spanishReply)
      setThinking(false)

      const updatedHistory = [...newMessages, { role: 'model', parts: [spanishReply] }]
      setHistory(updatedHistory)
      historyRef.current = updatedHistory

      // Speak only the Spanish — strip out any bracketed English hints
      speakSpanish(stripBrackets(spanishReply))

    } catch (error) {
      console.error('Error:', error)
      setThinking(false)
      setStatus('Error talking to Gemini. Try again.')
    }
  }

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      window.setTimeout(() => setStatus('Speech not supported. Use Chrome or Edge.'), 0)
      return
    }

    const recognition = new SpeechRecognition()
    recognition.continuous     = false
    recognition.interimResults = true
    recognition.lang           = 'es-MX'

    recognition.onstart = () => {
      console.log('Recognition started')
    }

    recognition.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript
        if (e.results[i].isFinal) {
          accumulatedRef.current += text + ' '
        } else {
          interim += text
        }
      }
      const display = (accumulatedRef.current + interim).trim()
      if (display) setLiveText(display)
    }

    recognition.onerror = (e) => {
      console.log('Error:', e.error)
      if (e.error === 'not-allowed') {
        setStatus('Microphone permission denied.')
        setListening(false)
        listeningRef.current = false
      }
    }

    recognition.onend = () => {
      if (!listeningRef.current) return
      setTimeout(() => {
        if (listeningRef.current) {
          try {
            recognition.start()
          } catch (e) {
            console.log('Restart error:', e.message)
          }
        }
      }, 100)
    }

    recognitionRef.current = recognition

    return () => {
      listeningRef.current = false
      try { recognition.abort() } catch { return }
    }
  }, [])

  function startListening() {
    if (listening || speaking || thinking) return
    if (!recognitionRef.current) return

    accumulatedRef.current = ''
    setLiveText('')
    setTranscript('')
    setReply('')
    listeningRef.current = true

    try {
      recognitionRef.current.start()
      setListening(true)
      setStatus('Listening... speak now')
    } catch (e) {
      console.error('Start error:', e)
      setStatus("Couldn't start. Tap to try again.")
      listeningRef.current = false
    }
  }

  function stopListening() {
    if (!listeningRef.current) return

    listeningRef.current = false
    setListening(false)

    try { recognitionRef.current.stop() } catch { return }

    setTimeout(() => {
      const fullText = accumulatedRef.current.trim()

      if (!fullText) {
        setStatus("I didn't hear anything. Tap to try again.")
        setLiveText('')
        return
      }

      setTranscript(fullText)
      setLiveText('')
      setStatus('Processing...')
      trackVoiceActivity()
      sendToGemini(fullText)
    }, 300)
  }

  function speakSpanish(text) {
    setSpeaking(true)
    setStatus('Gemini is speaking...')
    window.speechSynthesis.cancel()

    const utterance  = new SpeechSynthesisUtterance(text)
    utterance.lang   = 'es-ES'
    utterance.rate   = 0.95
    utterance.pitch  = 1.0
    utterance.volume = 1.0

    const voices = window.speechSynthesis.getVoices()
    const spanishVoice = voices.find(v =>
      v.lang.startsWith('es') &&
      (v.name.includes('Google') || v.name.includes('Microsoft'))
    ) || voices.find(v => v.lang.startsWith('es'))

    if (spanishVoice) utterance.voice = spanishVoice

    utterance.onend   = () => { setSpeaking(false); setStatus('Tap the mic to speak again') }
    utterance.onerror = () => { setSpeaking(false); setStatus('Tap the mic to speak') }

    window.speechSynthesis.speak(utterance)
  }

  function stopSpeaking() {
    window.speechSynthesis.cancel()
    setSpeaking(false)
    setStatus('Tap the mic to speak')
  }

  const micColor  = listening ? '#E24B4A' : speaking ? '#1D9E75' : thinking ? '#EF9F27' : '#500000'
  const micIcon   = listening ? '🎙️' : speaking ? '🔊' : thinking ? '⏳' : '🎤'
  const micShadow = listening
    ? '0 0 0 20px rgba(226,75,74,0.15)'
    : speaking  ? '0 0 0 20px rgba(29,158,117,0.15)'
    : thinking  ? '0 0 0 20px rgba(239,159,39,0.15)'
    : '0 4px 12px rgba(80,0,0,0.2)'

  return (
    <div style={{
      padding:       '24px',
      display:       'flex',
      flexDirection: 'column',
      alignItems:    'center',
      minHeight:     '500px'
    }}>

      {/* Title */}
      <p style={{
        fontFamily:    "'Oswald', sans-serif",
        fontSize:      '20px',
        fontWeight:    '700',
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        color:         '#500000',
        marginBottom:  '4px'
      }}>
        Voice Chat
      </p>
      <p style={{
        fontFamily:   "'Open Sans', sans-serif",
        fontSize:     '13px',
        color:        '#888',
        marginBottom: '28px',
        textAlign:    'center'
      }}>
        Speak Spanish or English — Gemini always replies in Spanish
      </p>

      {/* Level indicator */}
      <div style={{
        background:   '#f0eaea',
        borderRadius: '20px',
        padding:      '4px 14px',
        marginBottom: '12px',
        fontSize:     '12px',
        color:        '#500000',
        fontFamily:   "'Open Sans', sans-serif",
        fontWeight:   '600'
      }}>
        Level: {level}
      </div>

      {/* Status pill */}
      <div style={{
        background:   thinking ? '#f5f0f0' : speaking ? '#E1F5EE' : '#f0f0f0',
        borderRadius: '20px',
        padding:      '8px 20px',
        marginBottom: '24px',
        minWidth:     '200px',
        textAlign:    'center',
        transition:   'background 0.3s'
      }}>
        <p style={{
          fontFamily: "'Open Sans', sans-serif",
          fontSize:   '13px',
          color:      thinking ? '#500000' : speaking ? '#085041' : '#555',
          fontWeight: thinking || speaking ? '600' : '400'
        }}>
          {status}
        </p>
      </div>

      {/* Sound bars when listening */}
      {listening && (
        <div style={{
          display:      'flex',
          alignItems:   'flex-end',
          gap:          '4px',
          marginBottom: '12px',
          height:       '32px'
        }}>
          {[1, 2, 4, 5, 4, 3, 5, 2, 1].map((h, i) => (
            <div key={i} style={{
              width:        '4px',
              height:       `${h * 5}px`,
              background:   '#500000',
              borderRadius: '2px',
              animation:    `soundBar ${0.3 + i * 0.07}s ease-in-out infinite alternate`,
            }} />
          ))}
          <style>{`
            @keyframes soundBar {
              from { transform: scaleY(0.2); opacity: 0.4; }
              to   { transform: scaleY(1.5); opacity: 1; }
            }
          `}</style>
        </div>
      )}

      {/* Mic button */}
      <div
        onClick={
          speaking  ? stopSpeaking  :
          listening ? stopListening :
                      startListening
        }
        style={{
          width:          '120px',
          height:         '120px',
          borderRadius:   '50%',
          background:     micColor,
          display:        'flex',
          alignItems:     'center',
          justifyContent: 'center',
          cursor:         thinking ? 'not-allowed' : 'pointer',
          marginBottom:   '12px',
          transform:      listening ? 'scale(1.1)' : 'scale(1)',
          transition:     'all 0.2s',
          boxShadow:      micShadow,
          userSelect:     'none',
          opacity:        thinking ? 0.8 : 1
        }}
      >
        <span style={{ fontSize: '42px' }}>{micIcon}</span>
      </div>

      <p style={{
        fontFamily:   "'Open Sans', sans-serif",
        fontSize:     '13px',
        color:        '#888',
        marginBottom: '16px'
      }}>
        {listening  ? 'Tap again when done speaking' :
         speaking   ? 'Tap to stop'                  :
         thinking   ? 'Thinking...'                  :
                      'Tap to speak'}
      </p>

      {/* Live text while speaking */}
      {listening && liveText && (
        <div style={{
          background:   'rgba(80,0,0,0.05)',
          border:       '1px dashed #500000',
          borderRadius: '4px',
          padding:      '10px 14px',
          marginBottom: '12px',
          width:        '100%',
          maxWidth:     '400px'
        }}>
          <p style={{
            fontFamily:    "'Oswald', sans-serif",
            fontSize:      '10px',
            color:         '#500000',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            marginBottom:  '4px'
          }}>
            Hearing...
          </p>
          <p style={{
            fontFamily: "'Open Sans', sans-serif",
            fontSize:   '14px',
            color:      '#333',
            fontStyle:  'italic',
            lineHeight: '1.5'
          }}>
            {liveText}
          </p>
        </div>
      )}

      {/* What user said */}
      {transcript && !listening && (
        <div style={{
          background:   '#f5f0f0',
          borderTop:    '3px solid #500000',
          padding:      '12px 16px',
          marginBottom: '10px',
          width:        '100%',
          maxWidth:     '400px'
        }}>
          <p style={{
            fontFamily:    "'Oswald', sans-serif",
            fontSize:      '10px',
            fontWeight:    '600',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color:         '#500000',
            marginBottom:  '6px'
          }}>
            You Said
          </p>
          <p style={{
            fontFamily: "'Open Sans', sans-serif",
            fontSize:   '14px',
            color:      '#202020',
            lineHeight: '1.5'
          }}>
            {transcript}
          </p>
        </div>
      )}

      {/* Thinking indicator */}
      {thinking && (
        <div style={{
          background:   '#f8f8f8',
          padding:      '12px 16px',
          marginBottom: '10px',
          width:        '100%',
          maxWidth:     '400px',
          textAlign:    'center'
        }}>
          <p style={{
            fontFamily: "'Open Sans', sans-serif",
            fontSize:   '13px',
            color:      '#999'
          }}>
            Gemini esta pensando en espanol...
          </p>
        </div>
      )}

      {/* Gemini reply — show full text including brackets for reading */}
      {reply && !thinking && (
        <div style={{
          background:   '#E1F5EE',
          borderTop:    '3px solid #1D9E75',
          padding:      '12px 16px',
          marginBottom: '10px',
          width:        '100%',
          maxWidth:     '400px'
        }}>
          <p style={{
            fontFamily:    "'Oswald', sans-serif",
            fontSize:      '10px',
            fontWeight:    '600',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color:         '#085041',
            marginBottom:  '6px'
          }}>
            Gemini Replied in Spanish
          </p>
          <p style={{
            fontFamily: "'Open Sans', sans-serif",
            fontSize:   '14px',
            color:      '#202020',
            lineHeight: '1.5'
          }}>
            {reply}
          </p>
        </div>
      )}

      <p style={{
        fontFamily: "'Open Sans', sans-serif",
        fontSize:   '11px',
        color:      '#bbb',
        marginTop:  '16px'
      }}>
        Level: {level} - Tap mic to start, tap again to send
      </p>

    </div>
  )
}

export default VoiceScreen