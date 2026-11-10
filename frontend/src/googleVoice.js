import axios from 'axios'

// Google (Gemini) text-to-speech via the backend's /api/tts/ — the same voices as the
// Listening section. Used by the Simulated Conversation (Chat (Voice) keeps the browser's
// voice); the caller falls back
// to the browser's speechSynthesis if this fails.
//
// Playback goes through an AudioContext the caller creates (or resumes) inside a click:
// audio that arrives after a network wait would otherwise be blocked by autoplay rules
// (Safari especially).

export function newAudioContext() {
  return new (window.AudioContext || window.webkitAudioContext)()
}

// texts → { voice, buffers } (decoded AudioBuffers, same order). Without a voice, `context`
// (the scenario, e.g. "…hablas con la Sra. Gómez…") lets the backend pick one of that gender.
export async function fetchSpeech(ctx, texts, voice, context) {
  const res = await axios.post('/api/tts/', { texts, voice, context })
  const buffers = await Promise.all(res.data.clips.map(({ audio }) => {
    const bytes = Uint8Array.from(atob(audio), c => c.charCodeAt(0))
    return ctx.decodeAudioData(bytes.buffer)
  }))
  return { voice: res.data.voice, buffers }
}

// Plays one decoded clip; resolves when it ends or is stopped. sourceRef.current lets the
// caller stop it with stopSpeech.
export function playBuffer(ctx, buffer, sourceRef) {
  return new Promise(resolve => {
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    source.onended = () => { if (sourceRef?.current === source) sourceRef.current = null; resolve() }
    if (sourceRef) sourceRef.current = source
    source.start()
  })
}

export function stopSpeech(sourceRef) {
  const source = sourceRef?.current
  if (source) {
    sourceRef.current = null
    try { source.stop() } catch { /* already stopped */ }
  }
}
