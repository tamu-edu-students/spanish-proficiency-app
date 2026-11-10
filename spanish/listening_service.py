"""BTLPT Domain I — Listening Comprehension.

One selection = a Spanish script (2-speaker dialogue, narrative, or informational talk),
spoken with Gemini text-to-speech, plus four multiple-choice questions in the prep
manual's mix (docs/BTLPT_Spanish_AI_Question_Generation_Guide.md §2): literal detail,
main idea/context, inference, interpretation. Selections are pre-generated into the
PromptPool (kind='listening'), audio included, so students don't wait on generation.
"""
import base64
import io
import random
import re
import unicodedata
import wave

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

SCRIPT_MODEL = getattr(settings, "GEMINI_GRADING_MODEL", "gemini-2.5-flash")
# ponytail: TTS model ids move fast — override with GEMINI_TTS_MODEL when this one is renamed/GA'd.
TTS_MODEL = getattr(settings, "GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
TTS_SAMPLE_RATE = 24000   # Gemini TTS returns 16-bit mono PCM at 24 kHz
QUESTIONS = 4
GENERATION_ATTEMPTS = 2

# The code picks the type (as with correspondence formats) — left to choose, the model
# would always write a dialogue. Gemini multi-speaker TTS supports at most 2 voices.
SELECTION_TYPES = {
    "dialogue": (
        "an authentic-sounding CONVERSATION between exactly 2 people connected to a Texas "
        "public school (teacher + parent, teacher + principal, teacher + colleague, school "
        "counselor + parent, etc.), with natural conversational turns, a practical problem or "
        "situation, some information that is only implied, and a final request, decision or "
        "next step. Give each speaker an invented realistic full name with a title (Hispanic "
        "names are fine). 8-14 turns.",
        2,
    ),
    "narrative": (
        "a short spoken NARRATIVE or CULTURAL ACCOUNT told by one narrator — a legend, a "
        "historical or cultural account, or a tradition — with a chronological sequence, "
        "motivations, cultural references and a final outcome or explanation. The narrator is "
        "an invented person with a role (e.g. a teacher telling it to the class, a museum guide).",
        1,
    ),
    "informational": (
        "a short spoken INFORMATIONAL REPORT or MINI-LECTURE by one speaker on a content-area "
        "or education topic (science, environment, social studies, health, bilingual "
        "education, reading development…), with an identifiable topic, explanation of a "
        "process or issue, facts or examples, cause and effect, possibly a statistic or an "
        "expert reference, and broader implications. The speaker is an invented person with a "
        "role (e.g. a science specialist, a district literacy coach).",
        1,
    ),
}

LEVEL_LENGTH = {
    "A1": "80-120 words. Very simple, high-frequency vocabulary, short sentences, mostly present tense, slow and clear.",
    "A2": "120-170 words. Simple vocabulary, short connected sentences, some past and future forms.",
    "B1": "180-250 words. Everyday and some academic vocabulary, varied tenses, ideas linked with connectors.",
    "B2": "250-330 words. Rich academic vocabulary, complex sentences including subjunctive, nuanced attitude.",
}

QUESTION_MIX = """Then write exactly 4 multiple-choice questions, IN THIS ORDER:
1. literal / explicit detail (something directly stated)
2. main idea or setting/context (what it is mainly about, or where/who)
3. inference (what can reasonably be inferred, or what will most likely happen next)
4. interpretation — tone/attitude, purpose of what a speaker says, consequence, or how the
   speaker develops the point (examples, statistics, sequence, cause and effect)
Rules for questions and options:
- Questions and options in Spanish, at the student's level.
- 4 options each; exactly ONE is clearly best based on the audio; `answer_N` is that option's
  text copied EXACTLY.
- Distractors must be plausible and related to the selection: a true detail that doesn't answer
  the question, a related but narrower idea, a detail incorrectly connected, an inference that
  goes beyond the evidence, a reversed cause/effect. No absurd options, no option much longer
  than the others, nothing that needs outside knowledge.
- Do not make the answer obvious through repetition in the script.
- `explanation_N`: the rationale — 1-2 sentences in Spanish saying why the answer is right,
  citing what was said in the selection.
- `explanation_english_N`: a faithful English translation of `explanation_N`."""


class ListeningResponse(BaseModel):
    """Flat on purpose (parallel lists, numbered fields): nested models make Gemini's
    constrained decoding truncate output (see grading_service)."""
    title: str
    speaker_names: list[str]
    speaker_roles: list[str]
    speaker_genders: list[str]   # "female" | "male" — picks the TTS voice
    line_speakers: list[str]     # one per line, each one of speaker_names
    line_texts: list[str]
    question_1: str
    options_1: list[str]
    answer_1: str
    explanation_1: str
    explanation_english_1: str
    question_2: str
    options_2: list[str]
    answer_2: str
    explanation_2: str
    explanation_english_2: str
    question_3: str
    options_3: list[str]
    answer_3: str
    explanation_3: str
    explanation_english_3: str
    question_4: str
    options_4: list[str]
    answer_4: str
    explanation_4: str
    explanation_english_4: str


VOICES = {"female": ["Kore", "Leda", "Aoede"], "male": ["Charon", "Orus", "Puck"]}


def _client():
    if not settings.GEMINI_API_KEY:
        raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in environment.")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _script_prompt(level, selection_type):
    shape, speakers = SELECTION_TYPES[selection_type]
    return f"""You write BTLPT Spanish (190) Listening Comprehension practice for bilingual teachers in Texas.

Write ONE selection that will be read aloud: {shape}

Student level: CEFR {level}. Length: {LEVEL_LENGTH.get(level, LEVEL_LENGTH["B1"])}

Fields:
- title: a short Spanish title for the selection (shown only after the student answers).
- speaker_names / speaker_roles / speaker_genders: exactly {speakers} speaker(s); gender is
  "female" or "male".
- line_speakers / line_texts: the script, one entry per spoken turn or paragraph; each
  line_speakers entry is exactly one of speaker_names. Natural spoken Spanish — no stage
  directions, no sound effects, no brackets, no markdown.

{QUESTION_MIX}"""


def _validate(r: ListeningResponse, selection_type) -> list:
    """Questions as [{question, options, answer, explanation}] with options shuffled; raises
    ValueError on a malformed selection so the caller can retry."""
    speakers = SELECTION_TYPES[selection_type][1]
    if len(r.speaker_names) != speakers or len(set(r.speaker_names)) != speakers:
        raise ValueError(f"expected {speakers} distinct speakers, got {r.speaker_names}")
    if not r.line_texts or len(r.line_speakers) != len(r.line_texts):
        raise ValueError("script lines and speakers don't line up")
    if any(s not in r.speaker_names for s in r.line_speakers):
        raise ValueError("a line names an unknown speaker")
    questions = []
    for i in range(1, QUESTIONS + 1):
        options = [o.strip() for o in getattr(r, f"options_{i}")]
        answer = getattr(r, f"answer_{i}").strip()
        if len(options) != 4 or len(set(options)) != 4 or answer not in options:
            raise ValueError(f"question {i}: need 4 distinct options containing the answer")
        random.shuffle(options)   # the model tends to put the answer first
        questions.append({
            "question": getattr(r, f"question_{i}").strip(),
            "options": options,
            "answer": answer,
            "explanation": getattr(r, f"explanation_{i}").strip(),
            "explanation_english": getattr(r, f"explanation_english_{i}").strip(),
        })
    return questions


def _tts_label(name, i):
    """ASCII speaker tag for the TTS transcript ('Sra. Gómez' → 'SraGomez')."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z]", "", ascii_name) or f"Speaker{i + 1}"


def _pick_voices(genders):
    used, voices = set(), []
    for g in genders:
        pool = VOICES.get(g.lower().strip(), VOICES["female"])
        voice = next(v for v in pool if v not in used) if any(v not in used for v in pool) else pool[0]
        used.add(voice)
        voices.append(voice)
    return voices


def _speak(client, r: ListeningResponse) -> bytes:
    """Raw 24 kHz PCM for the whole selection — one voice per speaker."""
    voices = _pick_voices(r.speaker_genders)
    if len(r.speaker_names) == 1:
        text = ("Lee en voz alta, en español latinoamericano natural y a ritmo normal de habla, "
                "el siguiente texto:\n\n" + "\n\n".join(r.line_texts))
        speech = types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voices[0])))
    else:
        labels = [_tts_label(n, i) for i, n in enumerate(r.speaker_names)]
        if len(set(labels)) != len(labels):
            labels = [f"Speaker{i + 1}" for i in range(len(labels))]
        by_name = dict(zip(r.speaker_names, labels))
        script = "\n".join(f"{by_name[s]}: {t}" for s, t in zip(r.line_speakers, r.line_texts))
        text = (f"Lee esta conversación entre {labels[0]} y {labels[1]} en español latinoamericano "
                f"natural, como una conversación real en una escuela de Texas:\n\n{script}")
        speech = types.SpeechConfig(multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(speaker=label, voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))
                for label, voice in zip(labels, voices)
            ]))
    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=speech),
    )
    data = response.candidates[0].content.parts[0].inline_data.data
    return base64.b64decode(data) if isinstance(data, str) else data


def encode_audio(pcm: bytes):
    """(bytes, mime). MP3 keeps a 2-minute selection under ~1 MB in the pool; WAV fallback
    if the encoder isn't installed (5-6 MB, still plays)."""
    try:
        import lameenc
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(64)
        encoder.set_in_sample_rate(TTS_SAMPLE_RATE)
        encoder.set_channels(1)
        encoder.set_quality(2)
        return encoder.encode(pcm) + encoder.flush(), "audio/mpeg"
    except ImportError:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(TTS_SAMPLE_RATE)
            wav.writeframes(pcm)
        return buffer.getvalue(), "audio/wav"


def generate_selection(level="B1", selection_type=None):
    """A complete selection, ready to serve: script, questions (answers included — it's
    practice, checked client-side like the reading quiz) and base64 audio."""
    selection_type = selection_type or random.choice(list(SELECTION_TYPES))
    client = _client()
    last_error = None
    for _ in range(GENERATION_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=SCRIPT_MODEL,
                contents=_script_prompt(level, selection_type),
                config=types.GenerateContentConfig(
                    temperature=0.9,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    response_schema=ListeningResponse.model_json_schema(),
                ),
            )
            r = ListeningResponse.model_validate_json(response.text)
            questions = _validate(r, selection_type)
            break
        except (ValidationError, ValueError) as e:
            last_error = e
            print(f"Listening selection rejected, regenerating: {str(e)[:200]}")
    else:
        raise ValueError(f"Could not generate a listening selection: {last_error}")

    audio, mime = encode_audio(_speak(client, r))
    return {
        "level": level,
        "selection_type": selection_type,
        "title": r.title.strip(),
        "speakers": [{"name": n, "role": role} for n, role in zip(r.speaker_names, r.speaker_roles)],
        "script": [{"speaker": s, "text": t.strip()} for s, t in zip(r.line_speakers, r.line_texts)],
        "questions": questions,
        "audio": base64.b64encode(audio).decode(),
        "audio_mime": mime,
    }
