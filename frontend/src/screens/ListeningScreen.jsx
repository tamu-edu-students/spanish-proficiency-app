import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { strings } from '../i18n'

const API = '/api'
const MAROON = '#500000'

// BTLPT Domain I — Listening Comprehension, following the exam's playback rules:
// play once → preview the 4 questions → play a second time → answer one at a time →
// results with explanations and the transcript. No pausing or rewinding.
// Phases: start → loading → ready → play1 → preview → play2 → answer → results

const card = { background: '#fff', border: '1px solid #e0e0e0', borderRadius: '16px', padding: '20px', marginBottom: '16px' }
const primary = enabled => ({
  padding: '14px 32px', background: enabled ? MAROON : '#ccc', color: '#fff', border: 'none', borderRadius: '12px',
  fontSize: '16px', fontWeight: 500, cursor: enabled ? 'pointer' : 'not-allowed',
})
const LETTERS = ['A', 'B', 'C', 'D']

// Same rule as the task prompts in Writing/Speaking: English is an opt-in aid at A1/A2 only.
const ENGLISH_TOGGLE_LEVELS = ['A1', 'A2']

// The "Show English" pill used across the app (same look as GradingScreen's TaskPrompt).
function EnglishToggle({ english, t }) {
  const [showEnglish, setShowEnglish] = useState(false)
  return (
    <>
      <button
        onClick={() => setShowEnglish(s => !s)}
        aria-expanded={showEnglish}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '10px',
          padding: '6px 14px', minHeight: '32px', cursor: 'pointer',
          border: `2px solid ${MAROON}`, borderRadius: '999px',
          background: showEnglish ? MAROON : '#fff', color: showEnglish ? '#fff' : MAROON,
          fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '13px',
        }}
      >
        <span aria-hidden="true" style={{ fontFamily: "'Open Sans', sans-serif", fontWeight: 700, fontSize: '11px', border: '1px solid currentColor', borderRadius: '3px', padding: '0 4px', lineHeight: '16px' }}>EN</span>
        {showEnglish ? t.hideTranslation : t.showTranslation}
        <span aria-hidden="true">{showEnglish ? '▴' : '▾'}</span>
      </button>
      {showEnglish && (
        <p lang="en" style={{ borderLeft: `3px solid ${MAROON}`, paddingLeft: '12px', margin: '10px 0 0', color: '#666', fontSize: '15px', lineHeight: 1.5 }}>
          {english}
        </p>
      )}
    </>
  )
}

// Note-taking instructions for each playback, written like the task prompts in
// Writing/Speaking: Spanish first, English behind the toggle at A1/A2.
const LISTENING_NOTES = {
  first: {
    es: 'Instrucciones: Escucha la selección con atención y toma notas breves mientras escuchas: quién habla, de qué se trata, los detalles importantes (nombres, fechas, horas, números) y lo que se pide o se decide al final. Tus notas te ayudarán a responder las preguntas.',
    en: 'Instructions: Listen to the selection carefully and take brief notes as you listen: who is speaking, what it is about, the important details (names, dates, times, numbers) and what is requested or decided at the end. Your notes will help you answer the questions.',
  },
  second: {
    es: 'Instrucciones: Lee las preguntas de abajo antes de escuchar otra vez. Durante la segunda escucha, completa tus notas y busca la información que necesitas para responder cada pregunta.',
    en: 'Instructions: Read the questions below before listening again. During the second listening, complete your notes and look for the information you need to answer each question.',
  },
}

function ListeningNote({ which, level, t }) {
  const note = LISTENING_NOTES[which]
  return (
    <div style={{ background: '#faf8f8', border: '1px solid #f0e8e8', padding: '14px', fontSize: '15px', lineHeight: 1.6, marginBottom: '12px' }}>
      <p lang="es" style={{ color: MAROON, margin: 0 }}>{note.es}</p>
      {ENGLISH_TOGGLE_LEVELS.includes(level) && <EnglishToggle key={which} english={note.en} t={t} />}
    </div>
  )
}

// Why the correct answer is correct — Spanish always; at A1/A2 a "Show English" toggle
// reveals the English translation.
function Rationale({ q, allowEnglish, t }) {
  if (!q.explanation) return null
  return (
    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #f0e8e8' }}>
      <p style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '13px', color: MAROON, margin: '0 0 4px' }}>
        {t.listeningRationale}
      </p>
      <p lang="es" style={{ margin: 0, color: '#555', fontSize: '15px', lineHeight: 1.5 }}>{q.explanation}</p>
      {allowEnglish && q.explanation_english && <EnglishToggle english={q.explanation_english} t={t} />}
    </div>
  )
}

function audioUrlFrom(selection) {
  const bytes = Uint8Array.from(atob(selection.audio), c => c.charCodeAt(0))
  return URL.createObjectURL(new Blob([bytes], { type: selection.audio_mime || 'audio/mpeg' }))
}

function ListeningScreen({ level, lang }) {
  const t = strings(lang)
  const [phase, setPhase]         = useState('start')
  const [selection, setSelection] = useState(null)
  const [progress, setProgress]   = useState(0)
  const [current, setCurrent]     = useState(0)
  const [answers, setAnswers]     = useState([])
  const [error, setError]         = useState('')

  const audioRef = useRef(null)
  const urlRef   = useRef(null)

  function releaseAudio() {
    audioRef.current?.pause()
    audioRef.current = null
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    urlRef.current = null
  }

  useEffect(() => () => releaseAudio(), [])
  // a level change starts over
  useEffect(() => { releaseAudio(); setPhase('start'); setSelection(null) }, [level])

  async function load() {
    releaseAudio()
    setError(''); setAnswers([]); setCurrent(0); setPhase('loading')
    try {
      const res = await axios.post(`${API}/listening/`, { level })
      urlRef.current = audioUrlFrom(res.data)
      setSelection(res.data)
      setPhase('ready')
    } catch (e) {
      setError(e.response?.data?.error || t.listeningLoadFailed)
      setPhase('start')
    }
  }

  // One full, uninterruptible playback; `next` is the phase that follows it.
  function play(playPhase, next) {
    const audio = new Audio(urlRef.current)
    audioRef.current = audio
    setProgress(0)
    setPhase(playPhase)
    audio.ontimeupdate = () => audio.duration && setProgress(audio.currentTime / audio.duration)
    audio.onended = () => { setProgress(1); setPhase(next) }
    audio.onerror = () => { setError(t.listeningAudioFailed); setPhase('start') }
    audio.play().catch(() => { setError(t.listeningAudioFailed); setPhase('start') })
  }

  function choose(option) {
    const next = [...answers]
    next[current] = option
    setAnswers(next)
  }

  function advance() {
    if (current + 1 < selection.questions.length) setCurrent(c => c + 1)
    else setPhase('results')
  }

  const questions = selection?.questions || []

  // ── START ──
  if (phase === 'start' || phase === 'loading') {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <div aria-hidden="true" style={{ fontSize: '48px', marginBottom: '16px' }}>🎧</div>
        <h2 style={{ fontSize: '19px', fontWeight: 600, color: '#333', marginBottom: '8px' }}>{t.listeningTitle}</h2>
        <p style={{ fontSize: '15px', color: '#666', lineHeight: 1.6, maxWidth: '560px', margin: '0 auto 16px' }}>{t.listeningIntro}</p>
        <div style={{ display: 'inline-block', background: '#E1F5EE', color: '#085041', borderRadius: '20px', padding: '4px 14px', fontSize: '15px', marginBottom: '24px' }}>
          Level: {level}
        </div>
        <br />
        <button onClick={load} disabled={phase === 'loading'} style={primary(phase !== 'loading')}>
          {phase === 'loading' ? t.listeningPreparing : t.listeningStart}
        </button>
        {error && <p role="alert" style={{ color: '#b00', fontSize: '15px', marginTop: '14px' }}>{error}</p>}
      </div>
    )
  }

  // ── RESULTS ──
  if (phase === 'results') {
    const score = questions.filter((q, i) => answers[i] === q.answer).length
    const speakerRole = Object.fromEntries((selection.speakers || []).map(s => [s.name, s.role]))
    return (
      <div style={{ padding: '16px' }}>
        <div style={{ ...card, textAlign: 'center' }}>
          <p style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', color: MAROON, fontSize: '15px', margin: '0 0 6px' }}>
            {t.score}
          </p>
          <p style={{ fontSize: '32px', fontWeight: 700, color: '#333', margin: 0 }}>{score}/{questions.length}</p>
        </div>

        {questions.map((q, i) => {
          const right = answers[i] === q.answer
          return (
            <div key={i} style={card}>
              <p style={{ fontSize: '14px', color: '#666', margin: '0 0 6px' }}>{t.question} {i + 1}</p>
              <p lang="es" style={{ fontSize: '17px', color: '#333', margin: '0 0 10px', lineHeight: 1.5 }}>{q.question}</p>
              <p lang="es" style={{ margin: '0 0 4px', color: right ? '#085041' : '#7B2323' }}>
                <span aria-hidden="true">{right ? '✓' : '✗'} </span>
                <strong>{t.listeningYourAnswer}:</strong> {answers[i] ?? '—'}
                <span className="sr-only" lang={lang}>{right ? t.correct : t.incorrect}</span>
              </p>
              {!right && (
                <p lang="es" style={{ margin: '0 0 4px', color: '#085041' }}>
                  <strong>{t.listeningCorrectAnswer}:</strong> {q.answer}
                </p>
              )}
              <Rationale q={q} allowEnglish={ENGLISH_TOGGLE_LEVELS.includes(level)} t={t} />
            </div>
          )
        })}

        <div style={card}>
          <h3 style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', color: MAROON, fontSize: '15px', margin: '0 0 4px' }}>
            {t.listeningTranscript}
          </h3>
          <p lang="es" style={{ fontWeight: 600, margin: '0 0 12px', color: '#333' }}>{selection.title}</p>
          <div lang="es" style={{ fontSize: '15px', lineHeight: 1.7, color: '#333' }}>
            {selection.script.map((line, i) => (
              <p key={i} style={{ margin: '0 0 10px' }}>
                {selection.speakers.length > 1 && (
                  <strong style={{ color: MAROON }}>{line.speaker}{speakerRole[line.speaker] ? ` (${speakerRole[line.speaker]})` : ''}: </strong>
                )}
                {line.text}
              </p>
            ))}
          </div>
          {selection.speakers.length === 1 && (
            <p lang="es" style={{ margin: '4px 0 0', color: '#666', fontSize: '14px' }}>— {selection.speakers[0].name}, {selection.speakers[0].role}</p>
          )}
        </div>

        <button onClick={load} style={{ ...primary(true), width: '100%' }}>{t.listeningNew}</button>
      </div>
    )
  }

  // ── ANSWER (one at a time, no feedback until the end, as in the exam) ──
  if (phase === 'answer') {
    const q = questions[current]
    return (
      <div style={{ padding: '16px' }}>
        <div style={{ marginBottom: '16px' }}>
          <span style={{ fontSize: '14px', color: '#666' }}>{t.question} {current + 1} {t.of} {questions.length}</span>
          <div style={{ height: '6px', background: '#f0e8e8', borderRadius: '3px', marginTop: '6px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${(current / questions.length) * 100}%`, background: MAROON, transition: 'width 0.3s ease' }} />
          </div>
        </div>
        <div style={card}>
          <p lang="es" style={{ fontSize: '18px', color: '#333', lineHeight: 1.6, margin: 0 }}>{q.question}</p>
        </div>
        <div role="radiogroup" aria-label={q.question} lang="es" style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
          {q.options.map((option, i) => {
            const on = answers[current] === option
            return (
              <button
                key={i}
                role="radio"
                aria-checked={on}
                onClick={() => choose(option)}
                style={{ padding: '14px 16px', background: on ? '#f9f0f0' : '#fff', border: `${on ? 2 : 1}px solid ${on ? MAROON : '#8a8a8a'}`, borderRadius: '12px', color: '#333', fontSize: '15px', textAlign: 'left', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px' }}
              >
                <span style={{ width: '24px', height: '24px', borderRadius: '50%', flexShrink: 0, background: on ? MAROON : '#f0f0f0', color: on ? '#fff' : '#666', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', fontWeight: 500 }}>
                  {LETTERS[i]}
                </span>
                {option}
              </button>
            )
          })}
        </div>
        <button onClick={advance} disabled={!answers[current]} style={{ ...primary(!!answers[current]), width: '100%' }}>
          {current + 1 < questions.length ? t.nextQuestion : t.seeResults}
        </button>
      </div>
    )
  }

  // ── READY / PLAYING / PREVIEW ──
  const playing = phase === 'play1' || phase === 'play2'
  return (
    <div style={{ padding: '16px' }}>
      <div role="status" aria-live="polite" style={{ ...card, border: `2px solid ${MAROON}` }}>
        <p style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '13px', color: '#666', margin: '0 0 6px' }}>
          {phase === 'ready' || phase === 'play1' ? t.listeningFirstPlay : t.listeningSecondPlay}
        </p>
        <ListeningNote which={phase === 'ready' || phase === 'play1' ? 'first' : 'second'} level={level} t={t} />
        <p style={{ fontSize: '18px', fontWeight: 600, color: MAROON, margin: '0 0 12px' }}>
          {playing ? `🔊 ${t.listeningPlaying}` : phase === 'ready' ? t.listeningReady : t.listeningPreviewHint}
        </p>
        {(playing || phase === 'preview') && (
          <div style={{ height: '6px', background: '#eee', borderRadius: '3px', marginBottom: '12px' }}>
            <div style={{ height: '100%', width: `${progress * 100}%`, background: MAROON, borderRadius: '3px', transition: 'width 0.25s linear' }} />
          </div>
        )}
        {phase === 'ready' && <button onClick={() => play('play1', 'preview')} style={primary(true)}>▶ {t.listeningPlayFirst}</button>}
        {phase === 'preview' && <button onClick={() => play('play2', 'answer')} style={primary(true)}>▶ {t.listeningPlaySecond}</button>}
      </div>

      {/* the exam lets candidates preview the questions before the second playback */}
      {(phase === 'preview' || phase === 'play2') && (
        <div style={card}>
          <h3 style={{ fontFamily: "'Oswald', sans-serif", textTransform: 'uppercase', letterSpacing: '0.08em', color: MAROON, fontSize: '15px', margin: '0 0 10px' }}>
            {t.listeningPreviewTitle}
          </h3>
          <ol lang="es" style={{ margin: 0, paddingLeft: '22px', lineHeight: 1.6, color: '#333' }}>
            {questions.map((q, i) => (
              <li key={i} style={{ marginBottom: '10px' }}>
                {q.question}
                <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0', color: '#555', fontSize: '15px' }}>
                  {q.options.map((o, j) => <li key={j}>{LETTERS[j]}. {o}</li>)}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      )}
      {error && <p role="alert" style={{ color: '#b00', fontSize: '15px' }}>{error}</p>}
    </div>
  )
}

export default ListeningScreen
