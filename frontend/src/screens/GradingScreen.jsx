import { useState, useRef, useEffect, useCallback } from 'react'
import axios from 'axios'

const API = '/api'

const MAROON = '#500000'

const NOTES = {
  essay: 'Minimum 75 words. No upper limit.',
  audio: 'Speak for 50–120 seconds.',
}

// The task prompt is generated per student level, then sent back with the
// answer so the grader scores against the prompt the student actually saw.
function useTask(kind, level) {
  const [task, setTask]       = useState(null)
  const [loading, setLoading] = useState(true)

  const newTask = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.post(`${API}/grade/prompt/`, { kind, level })
      setTask(res.data)
    } catch {
      setTask({ spanish: 'No se pudo generar una pregunta. Inténtalo de nuevo.', english: '' })
    } finally {
      setLoading(false)
    }
  }, [kind, level])

   
  useEffect(() => { newTask() }, [newTask])

  return { task, loading, newTask }
}

const DIMENSION_LABELS = {
  task_completion:   'Task Completion',
  topic_development: 'Topic Development',
  language_use:      'Language Use',
  fluency:           'Fluency',
  coherency:         'Coherency',
}

function ScoreRow({ label, score, confidence }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
        <span>{label}</span>
        <span style={{ color: MAROON, fontWeight: 600 }}>
          {score}/3
          {confidence != null && (
            <span style={{ color: '#999', fontWeight: 400, marginLeft: '6px' }}>
              {Math.round(confidence * 100)}% conf.
            </span>
          )}
        </span>
      </div>
      <div style={{ height: '6px', background: '#eee', borderRadius: '3px' }}>
        <div style={{ height: '100%', width: `${(score / 3) * 100}%`, background: MAROON, borderRadius: '3px' }} />
      </div>
    </div>
  )
}

function Results({ result }) {
  const [lang, setLang] = useState('en')
  const scores = result.scores
  const max = Object.keys(scores).length * 3
  const total = Object.values(scores).reduce((a, b) => a + b, 0)

  return (
    <div style={{ background: '#fff', border: '1px solid #e0e0e0', padding: '20px', marginTop: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '16px' }}>
        <strong style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', color: MAROON }}>
          Score {total}/{max}
        </strong>
        <span style={{ fontSize: '12px', color: '#888' }}>
          {result.word_count != null && `${result.word_count} words · `}
          overall confidence {Math.round(result.overall_confidence * 100)}%
        </span>
      </div>

      {Object.entries(scores).map(([key, value]) => (
        <ScoreRow
          key={key}
          label={DIMENSION_LABELS[key] || key}
          score={value}
          confidence={result.confidence_scores?.[key]}
        />
      ))}

      <div style={{ marginTop: '18px', display: 'flex', gap: '8px' }}>
        {['en', 'es'].map(l => (
          <button
            key={l}
            onClick={() => setLang(l)}
            style={{
              padding: '4px 10px', fontSize: '11px', cursor: 'pointer',
              textTransform: 'uppercase', letterSpacing: '0.06em',
              border: `1px solid ${MAROON}`,
              background: lang === l ? MAROON : 'transparent',
              color: lang === l ? '#fff' : MAROON
            }}
          >
            {l === 'en' ? 'English' : 'Español'}
          </button>
        ))}
      </div>

      <p style={{ fontSize: '14px', lineHeight: 1.6, marginTop: '12px', whiteSpace: 'pre-wrap' }}>
        {lang === 'es' ? result.feedback_spanish : result.feedback}
      </p>

      {(result.reasoning || result.reasoning_spanish) && (
        <details style={{ marginTop: '12px', fontSize: '13px', color: '#555' }}>
          <summary style={{ cursor: 'pointer', color: MAROON }}>Grader reasoning</summary>
          <p style={{ marginTop: '8px', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {(lang === 'es' && result.reasoning_spanish) || result.reasoning}
          </p>
        </details>
      )}

      {result.transcription && (
        <details style={{ marginTop: '8px', fontSize: '13px', color: '#555' }}>
          <summary style={{ cursor: 'pointer', color: MAROON }}>Transcription</summary>
          <p style={{ marginTop: '8px', lineHeight: 1.6 }}>{result.transcription}</p>
          {result.transcription_english && (
            <p style={{ marginTop: '8px', lineHeight: 1.6, color: '#888' }}>{result.transcription_english}</p>
          )}
        </details>
      )}
    </div>
  )
}

function TaskPrompt({ task, note, loading, onNew }) {
  return (
    <div style={{ background: '#faf8f8', border: '1px solid #f0e8e8', padding: '14px', fontSize: '14px', lineHeight: 1.6 }}>
      {loading || !task ? (
        <p style={{ color: '#888' }}>Generando una pregunta...</p>
      ) : (
        <>
          <p style={{ color: MAROON }}>{task.spanish}</p>
          {task.english && <p style={{ color: '#888', fontSize: '13px', marginTop: '6px' }}>{task.english}</p>}
        </>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
        <span style={{ color: '#999', fontSize: '12px' }}>{note}</span>
        <button
          onClick={onNew}
          disabled={loading}
          style={{ background: 'none', border: 'none', color: MAROON, fontSize: '12px', cursor: loading ? 'not-allowed' : 'pointer', textDecoration: 'underline' }}
        >
          New prompt
        </button>
      </div>
    </div>
  )
}

function EssayTab({ sessionId, level, onGraded }) {
  const { task, loading: taskLoading, newTask } = useTask('essay', level)
  const [essay, setEssay]     = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState('')

  const words = essay.trim() ? essay.trim().split(/\s+/).length : 0

  async function submit() {
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await axios.post(`${API}/grade/essay/`, {
        essay,
        session_id:   sessionId,
        task_spanish: task?.spanish,
        task_english: task?.english,
      })
      setResult(res.data)
      onGraded()
    } catch (e) {
      setError(e.response?.data?.error || 'Grading failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <TaskPrompt task={task} note={NOTES.essay} loading={taskLoading} onNew={newTask} />
      <textarea
        value={essay}
        onChange={e => setEssay(e.target.value)}
        placeholder="Escribe tu ensayo aquí..."
        rows={12}
        style={{ width: '100%', marginTop: '12px', padding: '12px', border: '1px solid #e0e0e0', fontSize: '14px', lineHeight: 1.6, fontFamily: 'inherit', resize: 'vertical' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
        <span style={{ fontSize: '12px', color: words < 75 ? '#b06060' : '#5a8a5a' }}>
          {words} words {words < 75 && '(75 minimum)'}
        </span>
        <button
          onClick={submit}
          disabled={loading || !essay.trim()}
          style={{ padding: '10px 24px', background: loading || !essay.trim() ? '#ccc' : MAROON, color: '#fff', border: 'none', fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', cursor: loading || !essay.trim() ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Grading...' : 'Grade essay'}
        </button>
      </div>
      {error && <p style={{ color: '#b00', fontSize: '13px', marginTop: '10px' }}>{error}</p>}
      {result && <Results result={result} />}
    </>
  )
}

function AudioTab({ sessionId, level, onGraded }) {
  const { task, loading: taskLoading, newTask } = useTask('audio', level)
  const [recording, setRecording] = useState(false)
  const [blob, setBlob]           = useState(null)
  const [seconds, setSeconds]     = useState(0)
  const [loading, setLoading]     = useState(false)
  const [result, setResult]       = useState(null)
  const [error, setError]         = useState('')

  const recorderRef = useRef(null)
  const timerRef    = useRef(null)

  useEffect(() => () => clearInterval(timerRef.current), [])

  async function startRecording() {
    setError(''); setResult(null); setBlob(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks = []
      const recorder = new MediaRecorder(stream)
      recorder.ondataavailable = e => chunks.push(e.data)
      recorder.onstop = () => {
        setBlob(new Blob(chunks, { type: 'audio/webm' }))
        stream.getTracks().forEach(t => t.stop())
      }
      recorder.start()
      recorderRef.current = recorder
      setRecording(true)
      setSeconds(0)
      timerRef.current = setInterval(() => setSeconds(s => s + 1), 1000)
    } catch {
      setError('Microphone access denied. You can upload an audio file instead.')
    }
  }

  function stopRecording() {
    recorderRef.current?.stop()
    clearInterval(timerRef.current)
    setRecording(false)
  }

  async function submit() {
    setLoading(true); setError(''); setResult(null)
    const form = new FormData()
    // Backend picks the MIME type from the extension, so name the part accordingly.
    form.append('audio', blob, blob.name || 'recording.webm')
    form.append('session_id', sessionId)
    form.append('task_spanish', task?.spanish || '')
    form.append('task_english', task?.english || '')
    try {
      const res = await axios.post(`${API}/grade/audio/`, form)
      setResult(res.data)
      onGraded()
    } catch (e) {
      setError(e.response?.data?.error || 'Grading failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <TaskPrompt task={task} note={NOTES.audio} loading={taskLoading} onNew={newTask} />

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
        <button
          onClick={recording ? stopRecording : startRecording}
          style={{ padding: '10px 20px', background: recording ? '#b00' : MAROON, color: '#fff', border: 'none', fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', cursor: 'pointer' }}
        >
          {recording ? `Stop (${seconds}s)` : 'Record'}
        </button>

        <label style={{ fontSize: '13px', color: '#666', cursor: 'pointer' }}>
          or upload{' '}
          <input
            type="file"
            accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm"
            onChange={e => { setBlob(e.target.files[0] || null); setResult(null); setError('') }}
            style={{ fontSize: '12px' }}
          />
        </label>
      </div>

      {blob && !recording && (
        <div style={{ marginTop: '14px' }}>
          <audio controls src={URL.createObjectURL(blob)} style={{ width: '100%' }} />
          <button
            onClick={submit}
            disabled={loading}
            style={{ marginTop: '10px', padding: '10px 24px', background: loading ? '#ccc' : MAROON, color: '#fff', border: 'none', fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', cursor: loading ? 'not-allowed' : 'pointer' }}
          >
            {loading ? 'Grading...' : 'Grade recording'}
          </button>
        </div>
      )}

      {error && <p style={{ color: '#b00', fontSize: '13px', marginTop: '10px' }}>{error}</p>}
      {result && <Results result={result} />}
    </>
  )
}

function GradingScreen({ kind, sessionId, level }) {
  const [history, setHistory] = useState([])

  const loadHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/grade/history/`, { params: { session_id: sessionId, kind } })
      setHistory(res.data.submissions)
    } catch {
      setHistory([])
    }
  }, [sessionId, kind])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- state is set after the await, not synchronously
  useEffect(() => { loadHistory() }, [loadHistory])

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>

      {kind === 'essay'
        ? <EssayTab sessionId={sessionId} level={level} onGraded={loadHistory} />
        : <AudioTab sessionId={sessionId} level={level} onGraded={loadHistory} />}

      {history.length > 0 && (
        <div style={{ marginTop: '28px' }}>
          <h3 style={{ fontFamily: "'Oswald', sans-serif", fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.08em', color: MAROON, marginBottom: '10px' }}>
            Past {kind === 'essay' ? 'essays' : 'recordings'}
          </h3>
          {history.map(s => (
            <details key={s.id} style={{ background: '#fff', border: '1px solid #e0e0e0', padding: '10px 12px', marginBottom: '8px', fontSize: '13px' }}>
              <summary style={{ cursor: 'pointer' }}>
                {s.total_score}/{Object.keys(s.result.scores).length * 3}
                <span style={{ color: '#999' }}> · {new Date(s.created_at).toLocaleDateString()}</span>
              </summary>
              {s.task?.spanish && (
                <p style={{ marginTop: '8px', color: MAROON, fontSize: '12px' }}>{s.task.spanish}</p>
              )}
              <p style={{ marginTop: '8px', color: '#666', lineHeight: 1.6 }}>{s.text}</p>
              <Results result={s.result} />
            </details>
          ))}
        </div>
      )}
    </div>
  )
}

export default GradingScreen
