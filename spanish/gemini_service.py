from django.conf import settings
from google import genai
from google.genai import types


def build_system_prompt(level="B1", mode="chat"):
    guidance = {
        "A1": "Use very basic Spanish. Very short sentences. Always add English translation in parentheses after each Spanish word or phrase.",
        "A2": "Use simple Spanish. Common everyday words. Occasionally add English hints in parentheses for difficult words.",
        "B1": "Use intermediate Spanish. Full sentences with common verb tenses. No English hints.",
        "B2": "Use rich Spanish vocabulary. Complex sentences, subjunctive mood, idioms. No English at all.",
    }
    return f"""You are a friendly Spanish tutor.
RULES:
1. ALWAYS respond in Spanish, never in English.
2. Match CEFR level: {level}
3. {guidance.get(level, guidance["B1"])}
4. Correct grammar gently with "💡 Corrección:" at the end if needed.
5. Keep replies to 1-3 sentences.
6. Ask a follow-up question to keep conversation going.
7. Be encouraging and patient."""


def chat(messages, level="B1"):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    contents = []
    for msg in messages:
        contents.append({
            "role":  msg["role"],
            "parts": [{"text": msg["parts"][0]}]
        })
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(level),
            temperature=0.7,
        )
    )
    return response.text


def voice_chat(messages, level="B1"):
    """
    Faster chat function specifically for voice conversations.
    Uses shorter responses and simpler system prompt for speed.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    contents = []
    for msg in messages:
        contents.append({
            "role":  msg["role"],
            "parts": [{"text": msg["parts"][0]}]
        })

    voice_guidance = {
        "A1": "Use only 3-5 very basic Spanish words per sentence. Add English in parentheses.",
        "A2": "Use simple short Spanish sentences. Maximum 1 English hint per reply.",
        "B1": "Use natural conversational Spanish. No English.",
        "B2": "Use fluent natural Spanish. No English.",
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=f"""Eres un tutor de español amigable.
REGLAS IMPORTANTES:
1. SIEMPRE responde en español — nunca en inglés.
2. Nivel CEFR: {level}
3. {voice_guidance.get(level, voice_guidance["B1"])}
4. Respuestas MUY cortas — máximo 1-2 oraciones cortas.
5. Sé natural y conversacional como en una charla real.
6. NO corrijas gramática — solo conversa fluidamente.
7. Haz UNA pregunta corta al final para continuar la conversación.""",
            temperature=0.7,
            # Limit tokens for faster response
            max_output_tokens=80,
        )
    )
    return response.text


def generate_flashcards(topic, level="B1"):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"""Generate exactly 10 Spanish vocabulary flashcards about: {topic}

CEFR Level: {level}
- A1: Very basic everyday words only
- A2: Simple common words
- B1: Intermediate vocabulary
- B2: Advanced vocabulary, idioms

Return ONLY a valid JSON array — no markdown, no code blocks, no extra text:
[
  {{"word": "spanish_word", "translation": "english_meaning", "example": "Example sentence in Spanish using the word."}}
]

All 10 cards must be about {topic}. No text before or after the JSON array."""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.8)
    )
    return response.text


def generate_quiz(level="B1"):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = f"""Generate ONE Spanish fill-in-the-blank grammar question at CEFR level {level}.

CRITICAL RULES:
- The 4 options MUST all be DIFFERENT words — never repeat the same word
- Only ONE option should be correct
- The other 3 must be plausible but wrong
- Options should test real Spanish grammar knowledge for level {level}

Level guidance:
- A1: Present tense, basic verbs (ser, estar, tener, ir)
- A2: Present + simple past tense, common verbs
- B1: Past tenses (imperfecto, pretérito), reflexive verbs
- B2: Subjunctive, conditional, advanced grammar

Return ONLY valid JSON — no markdown, no code blocks, no extra text:
{{
  "sentence": "Spanish sentence with _____ where the answer goes",
  "options": ["correct_word", "wrong_word_2", "wrong_word_3", "wrong_word_4"],
  "answer": "correct_word",
  "explanation": "Brief explanation in Spanish why the answer is correct"
}}

VERIFY before returning: all 4 options are completely different words.
No text before or after the JSON."""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.9)
    )
    return response.text


def check_quiz_answer(question, user_answer, correct_answer, level="B1"):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
    prompt = f"""Give feedback on this Spanish grammar question in Spanish.

Question: {question}
User answered: {user_answer}
Correct answer: {correct_answer}
Was correct: {is_correct}

Write 1-2 sentences in Spanish:
- If correct: give encouragement and a quick grammar tip
- If wrong: explain clearly why {correct_answer} is correct and why {user_answer} is wrong

Level {level} — adjust complexity accordingly.
Reply in Spanish only."""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.5)
    )
    return response.text