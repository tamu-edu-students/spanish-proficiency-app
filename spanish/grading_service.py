"""AI grading service (essay + audio) using Gemini.

Ported from the spanish-grading-app FastAPI service; prompts kept verbatim.
"""
from pathlib import Path
from pydantic import BaseModel
from django.conf import settings
from google import genai
from google.genai import types

from .rubrics import SC_RUBRIC


# ---------------------------------------------------------------------------
# Pydantic response schemas passed to Gemini as response_schema.
#
# IMPORTANT: Gemini's constrained-decoding only works reliably with FLAT
# models. Nested BaseModel fields cause Gemini to silently truncate the
# output. All score / confidence sub-fields are therefore inlined here.
# ---------------------------------------------------------------------------

class EssayGradingResponse(BaseModel):
    """Flat schema for essay grading — used as Gemini response_schema."""
    word_count: int
    score_task_completion: int
    score_topic_development: int
    score_language_use: int
    feedback: str
    feedback_spanish: str
    reasoning: str
    reasoning_spanish: str
    confidence_task_completion: float
    confidence_topic_development: float
    confidence_language_use: float
    overall_confidence: float


class AudioGradingResponse(BaseModel):
    """Flat schema for audio grading — used as Gemini response_schema."""
    transcription: str
    transcription_english: str
    score_task_completion: int
    score_topic_development: int
    score_language_use: int
    score_fluency: int
    score_coherency: int
    feedback: str
    feedback_spanish: str
    confidence_task_completion: float
    confidence_topic_development: float
    confidence_language_use: float
    confidence_fluency: float
    confidence_coherency: float
    overall_confidence: float
    reasoning: str


# ---------------------------------------------------------------------------
# Task prompts
# ---------------------------------------------------------------------------

ORAL_TASK_TEMPLATE = """
TASK PROMPT GIVEN TO PARTICIPANTS:
{spanish}
({english})
Response time: minimum 50 seconds, maximum 120 seconds.
"""

ESSAY_TASK_TEMPLATE = """
WRITING TASK PROMPT:
{spanish}
({english})
Minimum word count: 75 words. There is no upper word limit.
"""

# The calibration anchors further down were written against the original fixed
# prompts (school uniforms / travel). They stay verbatim — they set severity,
# not topic — but the grader is told not to read them as topic requirements.
ANCHOR_DISCLAIMER = """
NOTE ON THE REFERENCE EXAMPLES BELOW: they were written for a different task
prompt. Use them ONLY to calibrate how severe each score level is. Judge
relevance against the TASK PROMPT above, never against the example's topic.
"""

# Fallback tasks — used when prompt generation is unavailable.
DEFAULT_ESSAY_TASK = {
    "spanish": "¿Deben los administradores de las escuelas requerir que los estudiantes usen uniformes escolares? Sustenta tus ideas indicando un mínimo de dos ventajas y dos desventajas de esta póliza escolar.",
    "english": "Should school administrators require students to wear school uniforms? Support your ideas by giving at least two advantages and two disadvantages of this school policy.",
}

DEFAULT_ORAL_TASK = {
    "spanish": "Describe brevemente sobre tus experiencias la última vez que viajaste o sobre un lugar a dónde te gustaría viajar.",
    "english": "Briefly describe your experience last time you traveled, or where you would like to travel.",
}


LEVEL_GUIDANCE = {
    "A1": "Very simple, concrete, everyday topic. Short prompt, basic vocabulary.",
    "A2": "Simple familiar topic (school, family, food, routines). Plain vocabulary.",
    "B1": "Everyday social or school issue the student can reason about.",
    "B2": "Abstract or civic topic requiring nuanced argument and precise vocabulary.",
}


class TaskPromptResponse(BaseModel):
    """Schema for a generated task prompt."""
    spanish: str
    english: str


# ---------------------------------------------------------------------------
# Grading service
# ---------------------------------------------------------------------------

class AIGradingService:
    """Service for AI-powered grading using Gemini."""

    def __init__(self):
        """Initialize the AI grading service."""
        key = getattr(settings, "GEMINI_API_KEY", None)
        self.client = genai.Client(api_key=key) if key else None
        self.model_name = getattr(settings, "GEMINI_GRADING_MODEL", "gemini-2.5-flash")

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_essay_prompt(self, essay_text: str, task: dict) -> str:
        """Build the grading prompt for written essay tasks."""
        word_count = len(essay_text.split())

        rubric_text = """
            SCORE 3 — HIGH
            Task Completion: Fully addresses and completes the task.
            Topic Development: Directly relates to the topic; topic well developed; supporting details are appropriate,accurate and effective.
            Language Use: Well organized and coherent; high degree of grammatical control; varied, precise vocabulary; very few spelling/punctuation errors; register appropriate.

            SCORE 2 — MID-HIGH
            Task Completion: Addresses and completes the task.
            Topic Development: Relates to the topic; most supporting details are well defined.
            Language Use: Organized but some parts not fully developed; moderate grammatical control; appropriate vocabulary with occasional errors; some spelling/punctuation errors that do not impede communication; register usually appropriate.

            SCORE 1 — MID-LOW
            Task Completion: Partially addresses the task; some required elements may be missing.
            Topic Development: Moderately relates to the topic; some details are vague.
            Language Use: Inadequately organized; frequent grammatical errors; limited vocabulary; frequent spelling/punctuation errors; register often inappropriate.

            SCORE 0 — LOW
            Task Completion: Partially addresses and/or partially completes the task.
            Topic Development: Minimally relates to the topic; supporting details mostly irrelevant.
            Language Use: Disorganized; numerous grammatical errors impede communication; insufficient vocabulary; pervasive spelling/punctuation errors.
            """

        return f"""You are a balanced Spanish language evaluator grading written essays for a BTLPT Spring Pre-Assessment.

                    {ESSAY_TASK_TEMPLATE.format(**task)}

                    STUDENT ESSAY (~{word_count} words):
                    ---
                    {essay_text}
                    ---

                    {rubric_text}

                    GRADING PHILOSOPHY:
                    - Grade fairly and accurately — follow the rubric closely. Do NOT automatically inflate scores.
                    - A score of 0 is only for completely blank, entirely off-topic, or utterly incomprehensible responses.
                    - Count advantages/disadvantages even if not formally labeled, but they must be clearly identifiable.
                    - Word count is informational only — ignore it for scoring.

                    HOW TO SCORE EACH DIMENSION — apply these PRECISELY:

                    ── TASK COMPLETION ──
                    Score 3: Essay MUST have ALL of these:
                      (a) A clear stated position/opinion answering the question in the TASK PROMPT
                          (NOT just describing pros/cons without taking a side)
                      (b) At least 2 distinct advantages AND 2 distinct disadvantages — each one must be
                          EXPLAINED with at least 1–2 sentences of reasoning, not merely named or labeled
                      (c) Organized as an essay (recognizable intro, body, conclusion — not just a list or run-on)
                      ✗ NOT a 3 if: any advantage or disadvantage is stated in a single phrase with no supporting
                          reasoning (e.g., "menos libertades" or "el precio" with no elaboration = not explained)
                      ✗ NOT a 3 if: the essay is under 75 words — insufficient length to fully complete a 2+2 task
                      ✗ NOT a 3 if: advantages/disadvantages are mentioned in passing within long run-on sentences
                          rather than presented as developed, distinct ideas
                    Score 2: Has a position + the required 2 advantages and 2 disadvantages identified, BUT:
                      • One or more points are stated with only a brief phrase or vague justification
                      • The essay is complete but some ideas lack depth or feel underdeveloped
                      • Structure is present but conclusion is minimal or missing
                    Score 1: ANY of these make it a Score 1:
                      • Writes about the topic as personal narrative/experience WITHOUT clearly answering the question asked
                      • Has only 1 advantage or 1 disadvantage (not the required 2+2)
                      • Entire essay is one unstructured paragraph or single run-on sentence with no clear intro/conclusion
                      • Lists ideas without any explanation or development
                    Score 0: Blank, completely off-topic, or incomprehensible

                    ── TOPIC DEVELOPMENT ──
                    Score 3: ALL of the following must be true:
                      ✔ EVERY advantage and disadvantage is explained with specific reasoning or a concrete example
                          — "specific" means the reader understands WHY it is an advantage/disadvantage,
                          not just THAT it is one
                      ✔ Ideas connect logically — the essay does not simply list points
                      ✔ No point is left as a bare phrase or single-clause statement
                      ✗ NOT a 3 if: any single advantage or disadvantage is stated without a reason or example
                          (e.g., "el precio de los uniformes" with no further elaboration = NOT explained)
                      ✗ NOT a 3 if: the explanation for a point is a vague generality
                          (e.g., "es bueno para los estudiantes," "trae muchos beneficios" — these add nothing)
                      ✗ NOT a 3 if: offering a proposed solution to a disadvantage substitutes for explaining
                          the disadvantage itself — solutions enrich a Score 3 essay but do NOT replace development
                    Score 2: Ideas are relevant and mostly clear, BUT:
                      • At least one point is thin — stated briefly without a full reason or example
                      • Overall, the reader understands the argument even where development is shallow
                      • Adding a solution/conclusion without fully developing the disadvantage = Score 2, not Score 3
                    Score 1: ANY of these:
                      • Ideas are merely named/listed without any explanation
                      • Content is a single long run-on with no logical sequencing
                      • Supporting ideas are too vague to evaluate
                    Score 0: No relevant content

                    ── LANGUAGE USE ──
                    Language Use is evaluated on THREE sub-dimensions — score ALL three before assigning the final LU score:

                    [A] ACADEMIC VOCABULARY
                      Score 3 requires: deliberate use of academic, formal, or topic-specific language.
                        Examples of academic vocabulary: "fomentar," "implementar," "cohesión," "discriminación
                        socioeconómica," "política educativa," "igualdad," "restricción," "carga económica,"
                        "entorno escolar," "identidad," "regulación," "promover," "reducir las desigualdades"
                        Examples of basic/conversational vocabulary (NOT Score 3): "bueno," "bonito," "malo,"
                        "creo que," "me gusta," "hay," "saben," "cosas," "mucho," "todo," "igual"
                      ✗ NOT a 3 if: the essay relies only on everyday conversational words — even with few errors,
                          basic vocabulary alone locks LU at Score 2 maximum.
                      Score 2: adequate vocabulary, understands the topic, but no academic register
                      Score 1: very basic vocabulary throughout — words a beginner would use

                    [B] WRITTEN FLUENCY (sentence structure and flow)
                      Evaluate sentence-level variety and syntactic complexity across the ENTIRE essay.
                      Count the number of syntactically complex sentences before assigning a score.

                      A "complex sentence" is any sentence that contains AT LEAST ONE of:
                        • Subordinate clause: introduced by "porque," "aunque," "cuando," "para que,"
                          "a pesar de que," "mientras que," "a menos que," "si bien"
                        • Conditional: "Si los administradores requirieran...," "Si se implementara..."
                        • Relative clause: "los estudiantes que...", "una política que...", "los padres cuyos..."
                        • Adverbial clause: "debido a que...", "con el fin de...", "ya que...", "puesto que..."

                      Score 3 requires ALL of the following:
                        ✔ At least 3 distinct complex sentence constructions (from the list above) spread
                            across the essay — not clustered in one sentence
                        ✔ Meaningful variation in sentence length — not all sentences are the same length
                        ✔ Ideas are connected WITHIN sentences as well as between them
                        ✗ NOT a 3 if: zero or only 1 complex sentence construction appears in the essay
                        ✗ NOT a 3 if: every sentence follows an identical Subject + Verb + Object or
                            Subject + Verb + Complement pattern, even if sentences are grammatically correct
                        ✗ NOT a 3 if: sentences are linked ONLY with coordinating conjunctions
                            ("y," "pero," "o") — coordination is NOT syntactic complexity
                        ✗ NOT a 3 if: 4 or more consecutive sentences begin with the same grammatical
                            subject (e.g., "Los uniformes ayudan... / Los uniformes reducen... /
                            Los uniformes permiten...") — this is structural repetition, not variety
                        ✗ NOT a 3 if: the essay reads like a bullet list — one idea per sentence with
                            no subordination or sentence-internal development

                      Score 2: some syntactic variety is present but not sustained throughout:
                        • 1–2 complex sentence constructions appear, but the rest are simple SVO sentences
                        • Sentence length varies somewhat (some longer, some shorter) but structure is
                          mostly simple
                        • Writing flows but feels mechanical or repetitive in pattern
                        • Example pattern that earns Score 2 (NOT 3):
                          "Los uniformes son buenos. Los estudiantes se concentran más. También, los
                          uniformes reducen las diferencias sociales. Sin embargo, cuestan mucho dinero."
                          → all SVO, no subordination, writing is choppy despite basic transitions

                      Score 1: writing is consistently choppy or structurally flat throughout:
                        • Zero complex sentence constructions — all sentences are simple SVO
                        • All sentences are short (under ~10 words) and follow the same pattern
                        • No subordination, no conditionals, no relative clauses anywhere
                        • Ideas are placed side by side rather than built upon each other
                        • Reads like disconnected bullet points

                      Score 0: sentence structure is so broken it impedes understanding

                    [C] TRANSITIONS AND COHESION
                      Score 3 requires: transitions used between EVERY major idea shift — not just one or two.
                        Required variety includes connectors from multiple categories:
                        • Addition: "además," "asimismo," "igualmente"
                        • Example: "por ejemplo," "es decir," "en particular"
                        • Contrast: "sin embargo," "no obstante," "a pesar de," "aunque"
                        • Cause/effect: "por lo tanto," "por eso," "debido a," "como resultado"
                        • Conclusion: "en conclusión," "en resumen," "finalmente"
                      ✗ NOT a 3 if: the only connectors used are "también," "y," "pero," or "sin embargo"
                          — this is minimal transition use, not the variety Score 3 requires
                      ✗ NOT a 3 if: ideas are listed one after another without cohesive linking language
                      Score 2: some transitions present but limited to 1–2 basic connectors, or used inconsistently
                      Score 1: no transitions at all, or only "y" / "pero" throughout

                    FINAL LU SCORE — assign based on the weakest sub-dimension AND error count:

                    STEP 1 — Count ALL spelling/grammar/accent errors in the essay:
                      Count each of these as one error:
                        • Missing accent on common words (niños→ninos, años→anos, más→mas, está→esta, etc.)
                        • Clear misspelling (espressar, escuala, rason, uniformez, a veses, desventajes, etc.)
                        • Wrong verb form / tense (viajaba when viajé is required, tengo when tenía is needed)
                        • Subject-verb agreement error ("desventajas incluye" instead of "incluyen")
                        • Missing or wrong article (omitting "los", "una", etc. where required)
                        • Gender/number agreement error ("el uniforme bonita", "muchos ventajas")
                      Do NOT double-count the same error in two places.

                    STEP 2 — Apply the error-count cap FIRST, then check sub-dimensions:
                      0–2 errors → error count does NOT cap; proceed to sub-dimension check
                      3–5 errors → LU CANNOT exceed Score 2, regardless of vocabulary/structure quality
                      6+ errors  → LU is Score 1, regardless of any other sub-dimension strengths

                    STEP 3 — Final LU score (after applying the error cap):
                      Score 3: ALL of A, B, C meet Score 3 requirements AND 0–2 errors (from Step 1)
                      Score 2: 3–5 errors (cap from Step 2), OR one or more of A, B, C falls below Score 3
                          (conversational vocabulary, choppy structure, or limited transitions all land here)
                      Score 1: 6+ errors (cap from Step 2), OR ANY of A, B, C is severely deficient
                      Score 0: errors so severe communication is impossible

                    SCORE CALIBRATION — use these anchors when scoring:
{ANCHOR_DISCLAIMER}

                    ── REFERENCE ESSAY → Score 2, 2, 2 (the most common overgrading pattern) ──
                    Pattern: "Yo creo que los administradores deben requerir uniformes. Una ventaja es
                    que los estudiantes saben que es tiempo de aprender. También, cuando todos usan
                    uniformes, no se puede distinguir sus clases sociales. Las desventajas incluyen
                    menos libertades para los estudiantes y el precio de los uniformes. Sin embargo,
                    los administradores pueden resolver estos problemas con algunos días sin uniformes
                    y recaudaciones de fondos." (~75+ words)

                      TC = 2 (NOT 3):
                        • Position is clear ✓ | 4 points identified ✓ | structure present ✓
                        • BUT: "menos libertades" is a label — no explanation of WHY it limits freedom
                        • BUT: "el precio" is a label — no explanation of WHY cost is a burden
                        • Offering solutions ("días sin uniformes," "recaudaciones") does NOT explain the
                          disadvantage — it jumps past the problem to the fix. TC stays at 2.

                      TD = 2 (NOT 3):
                        • 2 advantages have minimal reasoning | 2 disadvantages have ZERO reasoning
                        • Score 3 requires EVERY point to be explained — not 2 out of 4
                        • A concluding solution sentence cannot compensate for undeveloped disadvantages

                      LU = 2 (NOT 3):
                        • 3–5 errors (subject-verb agreement, article omission, punctuation) — cap prevents Score 3
                        • Vocabulary is conversational: "creo," "saben," "bonito," "bueno," no academic terms
                        • Transitions limited to "también" and "sin embargo" — insufficient variety for Score 3
                        • If this essay had 6+ errors instead, LU would be Score 1, not 2

                    ── WHAT A Score 3 TD LOOKS LIKE for disadvantages ──
                    Each disadvantage must have a reason: e.g., "Una desventaja es que el costo del
                    uniforme puede ser una carga económica para familias de bajos recursos, quienes ya
                    tienen dificultades para cubrir gastos básicos." That is an explained point.
                    "El precio de los uniformes" alone is NOT.

                    CRITICAL REMINDERS:
                    - Mentioning the topic is NOT the same as answering the question. The essay must take an explicit position on what the TASK PROMPT actually asks.
                    - A single run-on sentence with no punctuation = Score 1 for both TC and TD regardless of content mentioned.
                    - Count ALL grammar/spelling/accent errors carefully. 3–5 errors caps LU at Score 2. 6+ errors forces LU to Score 1, regardless of vocabulary or structure quality.
                    - A structurally complete essay (position + 2 advantages + 2 disadvantages) does NOT automatically earn Score 3. Each dimension must be evaluated independently.
                    - NAMING ≠ EXPLAINING: A bare phrase ("menos libertades," "el precio") with no WHY is not an explained point. TC and TD Score 3 require explanation, not just identification.
                    - SOLUTIONS ≠ DEVELOPMENT: Proposing a fix for a disadvantage you never explained earns TD=2, not TD=3.
                    - SHORT ESSAYS: An essay under 75 words almost never earns TC=3 AND TD=3 simultaneously — there simply is not enough content to fully explain 4 points.
                    - "Basic vocabulary" = everyday conversational words with no academic register. Score 3 for LU requires evidence of academic vocabulary (e.g., "fomentar," "discriminación," "cohesión," "implementar"). Conversational vocabulary → Score 2 at best for LU.

                    FEEDBACK INSTRUCTIONS:
                    - Feedback must be honest and match the scores. If TC=2 or TD=2, the feedback must explain what was missing — not praise what was present.
                    - Do NOT use phrases like "effectively addresses," "well-organized," "strong," or "each point is developed" unless the score for that dimension is 3.
                    - Always quote specific phrases from the essay to illustrate weaknesses (e.g., "'el precio de los uniformes' names a disadvantage but does not explain why cost is a burden for families").
                    - Feedback MUST explicitly address all three of the following whenever they are weak:
                        1. ACADEMIC VOCABULARY — tell the student which specific words are too basic and give
                           2–3 examples of academic alternatives they should use (e.g., "instead of 'cosas malas'
                           try 'consecuencias negativas' or 'implicaciones adversas'")
                        2. WRITTEN FLUENCY — count and cite the specific complex sentence structures that
                           ARE present, then name what is MISSING. If the score is 1 or 2:
                           • State how many complex constructions were found (e.g., "only 1 subordinate
                             clause was found in the entire essay")
                           • Quote the choppy pattern (e.g., "'Los uniformes son buenos. Los estudiantes
                             aprenden más. Los uniformes cuestan dinero.' — three consecutive short SVO
                             sentences with no subordination")
                           • Give 2–3 specific model sentences the student should emulate:
                             conditionals ("Si se requirieran uniformes, los estudiantes podrían..."),
                             relative clauses ("una política que beneficia a..."),
                             adverbial clauses ("debido a que las familias de bajos recursos...")
                        3. TRANSITIONS — list which transitions are missing and give specific examples the student
                           should use (e.g., "add 'además' to introduce second advantages, 'por lo tanto' to draw
                           conclusions, and 'por ejemplo' to introduce evidence")
                    - Feedback should read as constructive criticism that tells the student exactly what to do to reach the next level.

                    Respond using the exact fields requested. Keep feedback and reasoning concise (under 150 words each).
                    Also provide:
                    - `feedback_spanish`: the exact same feedback translated into Spanish (same detail level, same content).
                    - `reasoning_spanish`: the exact same reasoning translated into Spanish.
                    """

    def _build_audio_prompt(self, task: dict) -> str:
        """Build the grading prompt for oral recording tasks."""
        rubric = SC_RUBRIC
        criteria_text = ""
        for criterion in rubric.criteria:
            criteria_text += f"\nScore {criterion.score} ({criterion.level_name}):\n"
            criteria_text += f"  Task Completion: {'; '.join(criterion.task_completion)}\n"
            criteria_text += f"  Topic Development: {'; '.join(criterion.topic_development)}\n"
            criteria_text += f"  Language Use: {'; '.join(criterion.language_use)}\n"

        return f"""You are a strict, accurate Spanish language evaluator grading oral recordings for a BTLPT language proficiency assessment.

{ORAL_TASK_TEMPLATE.format(**task)}

RUBRIC: {rubric.name} — {rubric.description}

SCORING CRITERIA (0-3 scale):
{criteria_text}

GRADING PHILOSOPHY:
- Grade strictly and accurately — follow the rubric closely. Do NOT inflate or be charitable.
- A score of 0 is for recordings that are nearly silent, completely off-topic, or utterly incomprehensible.
- A score of 3 requires genuinely strong performance — not just "good enough." Most test-takers score 1 or 2, not 3.
- Hesitation, silence gaps, repetition, very short responses, and thin content should all lower your score.
- When in doubt between two scores, choose the LOWER one.

HOW TO SCORE EACH DIMENSION — apply these PRECISELY:

── TASK COMPLETION ──
Score 3: ALL of the following must be true:
  ✔ Clearly and fully addresses the task prompt, covering what it actually asks
  ✔ Response feels complete and well-organized — not just a string of disconnected statements
  ✔ Sustained real speech content of at least 60–90 seconds (pauses/silence don't count)
  ✔ No major gaps — the listener does not feel something important was left unsaid
  ✗ NOT a 3 if: speaker only touched ONE aspect with shallow treatment
  ✗ NOT a 3 if: there are long silences, trailing-off sentences, or speaker runs out of things to say mid-response
  ✗ NOT a 3 if: response is under 60 seconds of real speech regardless of quality
Score 2: Addresses the prompt AND meets ALL of:
  • Real speech content of at least 50 seconds (pauses excluded)
  • Includes at least 2 developed statements about the topic (not just naming things)
  • Stays on topic without major derailment
  (If the response is under 45 seconds of real content, it cannot be Score 2 — it is Score 1 at most)
Score 1: ANY of these make it a Score 1:
  • Under ~45 seconds of real speech / only 1–4 sentences with nothing substantive added
  • Names places but gives only generic, empty statements ("fue divertido", "vi muchas cosas") with nothing more
  • Barely addresses the task prompt even if on-topic
  • Spends most of the time in English or code-switching rather than Spanish
Score 0: Blank, silent, completely off-topic, or incomprehensible

── TOPIC DEVELOPMENT ──
Score 3: ALL of the following must be true:
  ✔ Provides SPECIFIC, well-developed details (e.g., named places WITH descriptions, activities WITH explanations, feelings WITH reasons, comparisons)
  ✔ Ideas connect logically and build on each other — not just a list
  ✔ The listener comes away with a vivid picture of what was described
  ✗ NOT a 3 if: ideas are a sequence of short statements without elaboration
  ✗ NOT a 3 if: the response repeats the same idea in slightly different words
  ✗ NOT a 3 if: details are mostly generic (e.g., "fue divertido", "me gustó mucho") without specifics
Score 2: Provides at least 2 concrete, specific details that go beyond just naming things; ideas are relevant but somewhat thin or vague in places; the listener understands the experience even if it lacks richness
Score 1: ANY of these:
  • Content is limited to naming places/activities with generic positive statements and nothing more
  • Response is too brief to develop any topic meaningfully (under ~45 seconds real speech)
  • Content consists mostly of filler phrases and generalities ("fue una experiencia nueva", "vi muchas cosas")
Score 0: No relevant content

── LANGUAGE USE ──
Score 3: ALL of the following must be true:
  ✔ Very few errors in grammar, verb conjugation, gender/number agreement, or vocabulary (≤3 total)
  ✔ No systematic pattern of errors
  ✔ Varied, precise vocabulary appropriate for the topic
  ✔ High fluency — smooth delivery, minimal hesitation, no long pauses
  ✔ Clear pronunciation throughout
  ✗ NOT a 3 if: there are 4+ grammatical errors (wrong tense, agreement, missing articles, etc.)
  ✗ NOT a 3 if: fluency is interrupted by multiple "uhm"/"este"/false starts across the recording
Score 2: Some errors in grammar, vocabulary, or pronunciation but communication is NOT impeded; moderate fluency; occasional hesitation or self-correction; vocabulary is adequate but not highly varied; roughly 4–7 errors total
Score 1: ANY of these:
  • 8+ grammatical errors across verb forms, agreement, vocabulary, or pronunciation
  • Very limited vocabulary (basic words repeated, heavy English borrowing / code-switching)
  • Low fluency — frequent long pauses, false starts, or labored expression throughout
  • Pronunciation significantly affects comprehension
Score 0: Errors so severe communication is impossible

── FLUENCY (oral delivery only) ──
Score fluency as a SEPARATE dimension from Language Use. Focus exclusively on delivery — pace, hesitation, and speech flow. Use the transcription as your evidence source.

BEFORE scoring, count these disfluency markers in the transcription:
  • Each "..." = a pause, silence gap, or audible hesitation
  • Each filler word: "um," "uh," "este," "eh," "como se llama," "o sea" (when used as filler)
  • Each false start: a phrase begun and abandoned before completion (e.g., "yo fui... yo, este... fui a...")
  • Each self-correction: saying one word then immediately replacing it (e.g., "comí... bebí... comí arroz")
  • Each English word inserted mid-Spanish sentence (code-switching mid-utterance)
Sum these to get the total disfluency count. Then assign:

Score 3: Smooth, natural delivery throughout.
  ✔ 0–2 total disfluency markers across the entire recording
  ✔ No false starts, no self-corrections
  ✔ No mid-sentence code-switching into English
  ✔ Pace is natural and consistent — no rushing or labored slowness
  ✗ NOT a 3 if: 3 or more total disfluency markers appear in the transcription
  ✗ NOT a 3 if: any false start or mid-utterance self-correction occurs
  ✗ NOT a 3 if: English words are inserted mid-Spanish sentence

Score 2: Mostly fluent but some disfluency is noticeable:
  • 3–6 total disfluency markers across the recording
  • At most 1–2 false starts OR 1–2 self-corrections
  • Occasional single English word inserted, but Spanish is otherwise maintained
  • Pace is mostly consistent; minor rushes or pauses do not derail the response
  • Listener follows without significant difficulty

Score 1: Frequent disfluency that disrupts flow:
  • 7 or more total disfluency markers across the recording, OR
  • Multiple false starts spread throughout, OR
  • Regular code-switching (full English phrases inserted into the response), OR
  • Long silences (3+ consecutive "..." in the transcription) that stall the response
  • Delivery feels labored or halting — the listener must work to follow

Score 0: Delivery is so hesitant or labored that it severely impedes understanding.

── COHERENCY (logical organization of ideas) ──
Score coherency as a SEPARATE dimension from Topic Development. Focus exclusively on how logically the ideas connect and flow — regardless of content richness.
Score 3: Ideas are clearly organized and logically sequenced. Transitions between ideas are smooth and intentional. The listener can easily follow the thread of the response. No abrupt topic jumps.
Score 2: Overall logic is followable, but some transitions are abrupt or ideas shift without clear connection. The response has a loose structure but is not disjointed.
Score 1: Response feels disorganized. Ideas appear in random order or jump between points without connectors. The listener must work to follow the argument.
Score 0: No discernible logical structure. Ideas are completely scattered or incoherent.

SCORE CALIBRATION — use these reference points when deciding:
{ANCHOR_DISCLAIMER}
  Score ~0 (avg 0.0): Nearly silent or completely incomprehensible. Non-Spanish speaker.
  Score ~0.3 (avg 0-0.45): NEAR-ZERO PERFORMER. Example: "La última vez que yo viajaba fue ir a otro país. Yo fui fue a Japón. Era una experiencia muy divertido y yo tenía muchas experiencias nuevas porque era otro país. Yo conocí otros culturas y yo vi muchos diferentes lugares. Y yo quiero viajar a Inglaterra para ver los castillos y los museos." — Speaker names two destinations (Japan, England) but provides ZERO concrete experience details: every descriptive phrase is pure filler ("experiencias nuevas", "vi muchos lugares", "conocer la cultura", "fue divertido"). Multiple grammar errors (viajaba, divertido for experiencia, otros culturas). This scores → TC=1, TD=0–1, LU=1 (avg ≈0.3–0.7). Do NOT award TC=2 or TD=2 just because two places are named — naming is not describing.
  Score ~0.6 (avg 0.6): Speaker briefly addresses the prompt with minimal development; response ~30–50 seconds; heavy errors throughout (wrong verb conjugations, gender errors, preposition misuse); limited vocabulary; no specific experiential details. → TC=1, TD=1, LU=1
  Score ~1.2 (avg 1.2): Speaker addresses the prompt with 50–70 seconds of real content; provides a few details but they are thin or semi-generic; moderately frequent errors that don't fully impede communication. → TC=1–2, TD=1–2, LU=1–2
  Score ~2.4 (avg 2.4): Speaker provides a well-developed narrative 60–90+ seconds; specific details with names, descriptions, and some elaboration; errors are present but do not impede communication; good fluency overall. → TC=2–3, TD=2–3, LU=2
  Score ~3.0 (avg 3.0): Rich, fluent, well-organized response with extensive specific details; very few errors (≤3); natural delivery. Rare. → TC=3, TD=3, LU=3

CRITICAL REMINDERS:
- Naming two destinations with generic filler IS NOT Task Completion Score 2. "Fui a Japón, tuve muchas experiencias nuevas, vi muchos lugares" + "quiero ir a Inglaterra para ver los castillos" contains ZERO real content — this is Score 1 for TC and Score 0–1 for TD.
- "Specific details" means sensory, experiential, or situational content. "Fue divertido", "tuve experiencias nuevas", "vi muchos lugares", "conocer la cultura" are all empty filler — they add NO information. A response consisting entirely of such phrases scores TD=0–1.
- TC=2 requires at least 2 developed statements (not just names or filler). TD=2 requires at least 2 concrete specific details.
- HOLISTIC LANGUAGE CAP: If Language Use deserves a score of 1 (pervasive grammatical errors, limited vocabulary, and/or impeded fluency across the entire response), then TC and TD CANNOT be 3. Cap them at 2 maximum. Severe language errors inevitably impair how well the task is completed and how well the topic is developed from the listener's perspective. A score pattern of TC=3, TD=3, LU=1 is NEVER valid on this assessment.
- TC=3 and TD=3 simultaneously for a response where the listener regularly struggles to understand due to LU errors is ALWAYS an error.
- A response under ~50 seconds of real speech cannot score 3 on TC or TD regardless of quality.
- Language score must reflect the full pattern of errors across the ENTIRE recording, not just the best sentences.

YOUR TASK:
1. Transcribe the Spanish audio completely and accurately (include pauses as "..." and English words as-is).
2. Carefully count errors in the transcription before assigning Language Use score.
3. Evaluate on FIVE dimensions: Task Completion, Topic Development, Language Use, Fluency, Coherency.
4. Assign scores (0-3) per dimension based on the rubric above — be strict and apply the "NOT a 3" disqualifiers.
5. Provide concise feedback in English (under 200 words) with SPECIFIC examples from the transcription, addressing all five dimensions. Store this in the `feedback` field.
6. Translate that same feedback into Spanish and store it in the `feedback_spanish` field (same content, same detail level, just in Spanish).
7. Assess confidence (0.0-1.0) for each score based on audio quality.
8. Briefly explain your overall reasoning (under 100 words).
9. Provide an English translation of the full transcription in the `transcription_english` field.

Respond using the exact fields requested.
"""

    # ------------------------------------------------------------------
    # Grading methods (sync — Django views are sync)
    # ------------------------------------------------------------------

    def _generate(self, contents, schema, temperature=0.2):
        if not self.client:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in environment.")
        return self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=schema.model_json_schema(),
            ),
        )

    def generate_task(self, kind: str, level: str = "B1") -> dict:
        """Generate a fresh, level-appropriate task prompt. Returns {spanish, english}."""
        if not self.client:
            return DEFAULT_ESSAY_TASK if kind == "essay" else DEFAULT_ORAL_TASK

        if kind == "essay":
            shape = (
                "an opinion question about a school, community or everyday policy — phrased so the "
                "writer must take a side AND give at least two advantages and two disadvantages. "
                "End the Spanish prompt with: 'Sustenta tus ideas indicando un mínimo de dos ventajas "
                "y dos desventajas.'"
            )
            example = DEFAULT_ESSAY_TASK["spanish"]
        else:
            shape = (
                "a speaking prompt asking the student to describe a personal experience or a "
                "hypothetical they can talk about for 50-120 seconds"
            )
            example = DEFAULT_ORAL_TASK["spanish"]

        prompt = f"""Write ONE fresh Spanish {kind} task prompt for a student at CEFR level {level}.

The prompt must be {shape}

Level {level} guidance: {LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["B1"])}

Pick a topic that is NOT this example, and not about school uniforms or travel: "{example}"

Return the prompt in Spanish, plus a faithful English translation."""

        response = self._generate(prompt, TaskPromptResponse, temperature=1.0)
        task = TaskPromptResponse.model_validate_json(response.text)
        return {"spanish": task.spanish, "english": task.english}

    def grade_essay(self, essay_text: str, task: dict = None) -> dict:
        """Grade a written essay against its task prompt. Returns scores, feedback and confidence."""
        task = task or DEFAULT_ESSAY_TASK
        response = self._generate(self._build_essay_prompt(essay_text, task), EssayGradingResponse)
        g = EssayGradingResponse.model_validate_json(response.text)
        return {
            # Local count — Gemini's own count drifts on tokenisation.
            "word_count": len(essay_text.split()),
            "scores": {
                "task_completion": g.score_task_completion,
                "topic_development": g.score_topic_development,
                "language_use": g.score_language_use,
            },
            "feedback": g.feedback,
            "feedback_spanish": g.feedback_spanish,
            "confidence_scores": {
                "task_completion": clamp_confidence(g.confidence_task_completion),
                "topic_development": clamp_confidence(g.confidence_topic_development),
                "language_use": clamp_confidence(g.confidence_language_use),
            },
            "overall_confidence": clamp_confidence(g.overall_confidence),
            "reasoning": g.reasoning,
            "reasoning_spanish": g.reasoning_spanish,
        }

    def grade_audio(self, audio_path: str, task: dict = None) -> dict:
        """Grade an oral recording against its task prompt."""
        task = task or DEFAULT_ORAL_TASK
        if not self.client:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in environment.")

        mime = MIME_TYPES.get(Path(audio_path).suffix.lower(), "audio/mp4")
        # Files API rather than inline bytes — older google-genai versions mishandle inline audio.
        gemini_file = self.client.files.upload(
            file=audio_path, config=types.UploadFileConfig(mime_type=mime)
        )
        try:
            response = self._generate([gemini_file, self._build_audio_prompt(task)], AudioGradingResponse)
        finally:
            try:
                self.client.files.delete(name=gemini_file.name)
            except Exception:
                pass

        g = AudioGradingResponse.model_validate_json(response.text)

        return {
            "transcription": g.transcription,
            "transcription_english": g.transcription_english,
            "scores": apply_lu_cap({
                "task_completion": g.score_task_completion,
                "topic_development": g.score_topic_development,
                "language_use": g.score_language_use,
                "fluency": g.score_fluency,
                "coherency": g.score_coherency,
            }),
            "feedback": g.feedback,
            "feedback_spanish": g.feedback_spanish,
            "confidence_scores": {
                "task_completion": clamp_confidence(g.confidence_task_completion),
                "topic_development": clamp_confidence(g.confidence_topic_development),
                "language_use": clamp_confidence(g.confidence_language_use),
                "fluency": clamp_confidence(g.confidence_fluency),
                "coherency": clamp_confidence(g.confidence_coherency),
            },
            "overall_confidence": clamp_confidence(g.overall_confidence),
            "reasoning": g.reasoning,
        }


def clamp_confidence(value: float) -> float:
    """Gemini occasionally returns confidences outside 0-1 (e.g. 5.0)."""
    return max(0.0, min(1.0, value))


def apply_lu_cap(scores: dict) -> dict:
    """Weak Language Use caps the other dimensions at 2 (mirrors human grading)."""
    if scores["language_use"] == 1:
        for key in ("task_completion", "topic_development"):
            scores[key] = min(scores[key], 2)
    return scores


MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}

service = AIGradingService()
