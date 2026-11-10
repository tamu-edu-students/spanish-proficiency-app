import re
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel


def build_system_prompt(level="B1", mode="chat", topic=None):
    guidance = {
        "A1": "Use very basic Spanish. Very short sentences. Always add English translation in parentheses after each Spanish word or phrase.",
        "A2": "Use simple Spanish. Common everyday words. Occasionally add English hints in parentheses for difficult words.",
        "B1": "Use intermediate Spanish. Full sentences with common verb tenses. No English hints.",
        "B2": "Use rich Spanish vocabulary. Complex sentences, subjunctive mood, idioms. No English at all.",
    }
    topic_rule = f"\n8. Keep the conversation focused on this topic: {topic}. Steer your questions and vocabulary toward it." if topic else ""
    return f"""You are a friendly Spanish tutor.
RULES:
1. ALWAYS respond in Spanish, never in English.
2. Match CEFR level: {level}
3. {guidance.get(level, guidance["B1"])}
4. Do NOT correct the student's grammar in your reply — corrections are shown to them separately.
5. Keep replies to 1-3 sentences.
6. Ask a follow-up question to keep conversation going.
7. Be encouraging and patient.{topic_rule}"""


# Correction is its own call, on the student's latest message only. Folding it into the
# reply call made it drift: later in a thread the model chatted and skipped corrections,
# and it missed opening ¿/¡. The stronger grading model at temperature 0 is stricter.
CORRECTION_MODEL = getattr(settings, "GEMINI_GRADING_MODEL", "gemini-2.5-flash")

CORRECTION_PROMPT = """You are a strict Spanish proofreader for a language learner. You receive ONE
message the student wrote. Check EVERY one of these and fix all errors you find:
- Opening ¿ and ¡: every question MUST start with ¿ and every exclamation with ¡ (Spanish
  requires both marks — "Me puedes ayudar?" is wrong, "¿Me puedes ayudar?" is right).
- Written accents (qué, cuál, cómo, dónde, más, está, sí, tú, él, también, examen/exámenes, …),
  including accents on question words.
- Capital letter at the start of each sentence; correct end punctuation.
- Spelling.
- Verb conjugation, tense and mood (indicative vs. subjunctive), ser/estar, por/para.
- Gender and number agreement; articles and prepositions.

Rules:
- Return `correction`: the student's WHOLE message rewritten correctly. Keep their meaning, words
  and tone — change only what is wrong. No explanation, no label, no quotes.
- If the message has no errors at all, return "".
- If the message is not in Spanish (e.g. written in English), return "".

Examples:
"Que es LPAC?" → "¿Qué es LPAC?"
"Me puedes compartir más?" → "¿Me puedes compartir más?"
"cuales son las razones que un estudiante pueda tomar el examen en español?"
→ "¿Cuáles son las razones por las que un estudiante puede tomar el examen en español?"
"""


class Correction(BaseModel):
    correction: str


_SENTENCE = re.compile(r"[^.?!]*[.?!]+|[^.?!]+$")


def _add_opening_marks(text):
    """Safety net for the mark the model most often misses: a sentence ending in ? or !
    with no ¿ / ¡ in it gets one at its start."""
    out = []
    for sentence in _SENTENCE.findall(text):
        body = sentence.lstrip()
        lead = sentence[:len(sentence) - len(body)]
        for close, opener in (("?", "¿"), ("!", "¡")):
            if body.rstrip().endswith(close) and opener not in body:
                body = opener + body
        out.append(lead + body)
    return "".join(out)


def correct_message(text):
    """The student's message rewritten correctly, or "" if it was already correct."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=CORRECTION_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=CORRECTION_PROMPT,
            temperature=0,
            response_mime_type="application/json",
            response_schema=Correction.model_json_schema(),
        )
    )
    correction = Correction.model_validate_json(response.text).correction.strip()
    if not correction and not _looks_spanish(text):
        return ""   # e.g. a message in English — don't bolt ¿ onto "What is LPAC?"
    fixed = _add_opening_marks(correction or text.strip())
    return "" if fixed == text.strip() else fixed


_SPANISH_WORDS = {
    "que", "qué", "cual", "cuál", "cuales", "cuáles", "como", "cómo", "donde", "dónde", "cuando",
    "cuándo", "por", "para", "el", "la", "los", "las", "es", "son", "un", "una", "del", "puedes",
    "puede", "tienes", "hay", "más", "mas", "muy", "pero", "con", "se", "yo", "tú", "usted",
}


def _looks_spanish(text):
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    return bool(re.search(r"[áéíóúñ¿¡]", text)) or any(w in _SPANISH_WORDS for w in words)


def _chat_reply(messages, level, topic):
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    contents = [{"role": msg["role"], "parts": [{"text": msg["parts"][0]}]} for msg in messages]
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=build_system_prompt(level, topic=topic),
            temperature=0.7,
        )
    )
    return response.text


def chat(messages, level="B1", topic=None):
    """Returns {'reply': str, 'correction': str}. The correction (of the student's latest
    message, every turn) runs in parallel with the reply so it adds no wait."""
    last = messages[-1]
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(correct_message, last["parts"][0]) if last["role"] == "user" else None
        reply = _chat_reply(messages, level, topic)
        try:
            correction = pending.result() if pending else ""
        except Exception as e:
            # a failed correction must never cost the student their reply
            print(f"Chat correction failed: {e}")
            correction = ""
    return {"reply": reply, "correction": correction}


def voice_chat(messages, level="B1"):
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
            system_instruction=f"""Eres un tutor de espanol amigable.
REGLAS IMPORTANTES:
1. SIEMPRE responde en espanol, nunca en ingles.
2. Nivel CEFR: {level}
3. {voice_guidance.get(level, voice_guidance["B1"])}
4. Respuestas MUY cortas, maximo 1-2 oraciones cortas.
5. Se natural y conversacional como en una charla real.
6. NO corrijas gramatica, solo conversa fluidamente.
7. Haz UNA pregunta corta al final para continuar la conversacion.""",
            temperature=0.7,
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

Return ONLY a valid JSON array, no markdown, no code blocks, no extra text:
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


def generate_quiz_batch(level="B1", count=10):
    """Generate all quiz questions in a single Gemini call."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    import random
    topics = {
        "A1": [
            "verb ser (to be - permanent)",
            "verb estar (to be - temporary)",
            "verb tener (to have)",
            "verb ir (to go)",
            "verb querer (to want)",
            "definite articles el/la/los/las",
            "indefinite articles un/una",
            "subject pronouns yo/tu/el",
            "numbers and quantities",
            "greetings and farewells",
            "verb hacer (to do/make)",
            "verb poder (can/to be able)",
            "verb comer/beber (eating verbs)",
            "colors and descriptions",
            "family members vocabulary",
            "days of the week",
            "weather expressions",
            "asking questions como/donde/cuando",
            "negation with no",
            "plural nouns",
        ],
        "A2": [
            "preterite tense regular verbs",
            "preterite tense irregular verbs",
            "gustar and similar verbs",
            "direct object pronouns",
            "reflexive verbs",
            "comparisons mas/menos que",
            "present progressive estar + gerund",
            "possessive adjectives",
            "prepositions a/de/en/con",
            "time expressions",
            "imperfect tense introduction",
            "verbs like encantar/molestar",
            "future with ir + a + infinitive",
            "adverbs of frequency",
            "superlatives el mas/menos",
            "double negation nunca/nadie/nada",
            "verbs with prepositions",
            "commands informal tu",
            "hace + time expressions",
            "ser vs estar with adjectives",
        ],
        "B1": [
            "preterite vs imperfect contrast",
            "imperfect tense usage",
            "reflexive verbs advanced",
            "indirect object pronouns",
            "present subjunctive with querer que",
            "future tense regular verbs",
            "conditional tense",
            "por vs para",
            "ser vs estar advanced",
            "relative pronouns que/quien",
            "present perfect haber + participle",
            "pluperfect habia + participle",
            "passive se constructions",
            "verbs of emotion with subjunctive",
            "aunque + indicative or subjunctive",
            "commands formal usted",
            "diminutives and augmentatives",
            "reported speech",
            "adverbial clauses",
            "probability with future tense",
        ],
        "B2": [
            "present subjunctive in doubt/emotion",
            "imperfect subjunctive",
            "conditional perfect",
            "passive voice with ser",
            "subjunctive vs indicative contrast",
            "advanced por/para",
            "idiomatic expressions",
            "gerund vs infinitive",
            "compound tenses haber",
            "subjunctive in time clauses",
            "sequence of tenses in subjunctive",
            "si clauses hypothetical",
            "nominalization of adjectives",
            "absolute superlative isimo",
            "passive voice with estar",
            "causative hacer + infinitive",
            "periphrastic expressions",
            "concessive clauses",
            "purpose clauses para que",
            "temporal clauses cuando + subjunctive",
        ],
    }

    topic_list = topics.get(level, topics["B1"])
    selected_topics = random.sample(topic_list, min(count, len(topic_list)))
    topics_str = "\n".join(f"{i+1}. {t}" for i, t in enumerate(selected_topics))

    prompt = f"""Generate exactly {count} Spanish fill-in-the-blank grammar questions at CEFR level {level}.

Use these {count} different grammar topics, one per question:
{topics_str}

CRITICAL RULES:
- Each question must test a DIFFERENT grammar point
- The 4 options must all be DIFFERENT words within each question
- Only ONE option is correct per question
- The correct answer must be placed randomly among A/B/C/D positions, not always first
- Do NOT make the correct answer always option A
- All {count} sentences must be completely different from each other

Level guidance:
- A1: Present tense, basic verbs (ser, estar, tener, ir)
- A2: Present + simple past tense, common verbs
- B1: Past tenses (imperfecto, preterito), reflexive verbs
- B2: Subjunctive, conditional, advanced grammar

Return ONLY a valid JSON array of exactly {count} objects, no markdown, no code blocks, no extra text:
[
  {{
    "sentence": "Spanish sentence with _____ where the answer goes",
    "options": ["correct_word", "wrong_word_2", "wrong_word_3", "wrong_word_4"],
    "answer": "correct_word",
    "explanation": "Brief explanation in Spanish why the answer is correct"
  }}
]

No text before or after the JSON array."""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.95,
            max_output_tokens=4000,
        )
    )
    return response.text


def generate_reading_quiz(level="B1", count=5):
    """Generate an academic Spanish reading-comprehension passage with assessment-style questions."""

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = f"""
You are an expert Spanish-language assessment writer specializing in
academic reading comprehension and language-proficiency assessments.

Create ONE original Spanish reading-comprehension passage and exactly {count}
multiple-choice questions for a learner at CEFR level {level}.

The goal is NOT simply to test whether the learner can locate obvious facts.
The activity should resemble a formal academic language-proficiency assessment
in which the learner must understand, interpret, infer, and critically evaluate
a written text.

PASSAGE REQUIREMENTS
--------------------

Create an ORIGINAL, self-contained Spanish passage written in a formal,
academic or informational register.

The passage should resemble the kind of authentic written material that could
appear in an educational, cultural, scientific, historical, social, or
professional context.

Possible genres include:
- educational or explanatory article
- short biography
- historical or cultural article
- science or environmental article
- social or community issue
- informational magazine article
- school-related article
- cultural commentary
- short opinion/informational piece

Favor topics relevant to a bilingual educator in a Texas public school —
e.g. reading development, family involvement in education, bilingual
education, classroom strategies, notable Spanish-speaking writers/educators/
historical figures, Hispanic cultural traditions or literature, or academic
content-area subjects (science, social studies, geography, health) — while
still varying the genre and topic from passage to passage. Not every passage
needs to be school-related, but it should feel like something a bilingual
teacher preparing for a Texas certification exam would plausibly read.

Do NOT write a fictional story unless the topic naturally requires a
narrative/biographical format.

The passage should:
- develop a clear central idea
- contain multiple connected paragraphs
- include supporting details, examples, explanations, or evidence
- require the reader to connect information across sentences or paragraphs
- contain some information that must be inferred rather than directly stated
- use natural academic Spanish appropriate for the CEFR level
- avoid sounding like a language textbook exercise
- avoid overly simple sentence-by-sentence exposition
- avoid artificial repetition of the same vocabulary
- remain factually consistent within the passage

CEFR LEVEL GUIDANCE
-------------------

A1:
- 80-120 words
- very familiar topics
- simple sentence structures
- basic vocabulary
- mostly explicit information
- limited inference

A2:
- 120-160 words
- familiar educational, cultural, social, or everyday topics
- connected paragraphs
- some past/future forms
- simple explanations and relationships
- mostly literal comprehension with a small amount of inference

B1:
- 180-250 words
- 3-5 connected paragraphs
- informative or academic topic
- varied verb tenses
- moderately sophisticated vocabulary
- relationships between ideas
- some implied meaning
- basic analysis of purpose, tone, or conclusions

B2:
- 250-350 words
- 4-6 well-developed paragraphs
- academic, cultural, scientific, historical, or social topic
- nuanced arguments or explanations
- advanced but natural vocabulary
- cohesive devices and varied sentence structures
- information distributed across the passage
- meaningful inference, interpretation, tone, purpose, and point-of-view questions

QUESTION DESIGN
---------------

Generate exactly {count} questions.

The questions should collectively assess a variety of reading skills.

Use a mixture of the following question types:

1. Literal comprehension
   - stated details
   - sequence
   - specific information

2. Main idea / central theme
   - What is the central idea?
   - Which statement best summarizes the passage?

3. Inference
   - What can be inferred?
   - What is most likely true based on the passage?
   - What can be deduced from the author's statements?

4. Interpretation
   - What does a statement imply?
   - Why does the author mention a particular example?
   - What does a particular detail suggest?

5. Author's purpose
   - What is the purpose of the text?
   - Why was the text most likely written?

6. Tone / attitude
   - What is the tone of the passage?
   - How does the author present the topic?

7. Point of view
   - What perspective does the author take?
   - Which statement best reflects the author's position?

8. Cause and effect
   - What relationship between two events or ideas is suggested?

9. Supporting evidence
   - Which statement is supported by the passage?

10. Vocabulary in context
   - What does a word or expression most nearly mean in context?
   - Do NOT ask for dictionary definitions unrelated to the passage.

11. Text organization
   - What function does a paragraph or example serve?
   - How does a particular section contribute to the development of the text?

12. Application / conclusion
   - Based on the passage, what is most likely to happen or be true?

QUESTION DISTRIBUTION
---------------------

Do not make every question a simple factual-recall question.

For {count} questions:
- At least 1 question must test inference or deduction.
- At least 1 question must test main idea, purpose, tone, or point of view.
- At least 1 question must require understanding information from more than
  one part of the passage.
- The remaining questions may test literal comprehension, vocabulary,
  supporting evidence, cause/effect, or interpretation.

Question wording should resemble formal assessment language.

Useful Spanish question stems include:

- ¿Cuál es la idea principal del texto?
- ¿Cuál de las siguientes afirmaciones coincide con el contenido del texto?
- ¿Qué se puede inferir del texto?
- ¿Qué se puede deducir acerca de...?
- Según el texto, ¿cuál es la razón más probable por la que...?
- ¿Cuál es el propósito del texto?
- ¿Cuál es el tono del texto?
- ¿Qué sugiere el autor al afirmar que...?
- ¿Qué función cumple el ejemplo de...?
- ¿Cuál de las siguientes opciones explica mejor...?
- Según el texto, ¿qué consecuencia es más probable?
- En el contexto del segundo párrafo, ¿qué significa...?

Do not use the same question stem repeatedly.

ANSWER CHOICE DESIGN
--------------------

Each question must have exactly 4 options.

There must be exactly ONE defensible correct answer.

The three incorrect options must be plausible and related to the passage.

Create distractors using realistic assessment strategies:
- information mentioned elsewhere in the passage
- partially correct interpretations
- conclusions that go beyond the evidence
- details that are true but do not answer the question
- plausible misunderstandings of the author's argument

Do NOT create silly, obviously incorrect, or unrelated distractors.

Do NOT make the correct answer consistently longer, more specific,
more sophisticated, or grammatically different from the distractors.

Do not use "all of the above" or "none of the above."

Do not use trick questions.

Do not require outside knowledge to answer a question.

ANSWER VALIDATION
-----------------

Before returning the result, internally verify every question:

1. Is the correct answer directly supported or logically inferable from
   the passage?
2. Are the three distractors incorrect based on the passage?
3. Could a reasonable reader argue that another option is correct?
4. Does the question actually test the intended reading skill?
5. Is the answer based on the passage rather than outside knowledge?

If any question fails these checks, rewrite it.

ANSWER POSITION DISTRIBUTION
----------------------------

Distribute correct answers across A, B, C, and D.

Do not repeatedly place the correct answer in the same position.

For example, for 5 questions, a distribution such as:
B, D, A, C, B
is preferable to:
A, A, A, A, A.

EXPLANATIONS
------------

For every question, provide a brief explanation in Spanish.

The explanation must:
- identify why the correct answer is supported
- refer to the relevant idea or evidence in the passage
- explain briefly why the reasoning is valid

Do not simply repeat the correct option.

OUTPUT FORMAT
-------------

Return ONLY valid JSON. No markdown. No introductory text.

Use exactly this structure:

{{
    "passage": "Complete Spanish passage",
    "questions": [
        {{
            "question": "Question in Spanish",
            "type": "inference",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "answer": "Exact correct option text",
            "explanation": "Brief explanation in Spanish based on the passage."
        }}
    ]
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=5000
        )
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

Level {level}, adjust complexity accordingly.
Reply in Spanish only."""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.5)
    )
    return response.text