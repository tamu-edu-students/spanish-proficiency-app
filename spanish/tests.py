"""Tests for the AI grading features (generated prompts, essay + audio grading).

Gemini is never called — the client and `_generate` are stubbed so every test
exercises our own logic: prompt assembly, payload shaping, validation, storage.
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from . import grading_service as gs
from . import prompt_pool
from .models import PromptPool, Submission


def task_json(instructions='Pregunta nueva', instructions_english='New question', content='', **extra):
    """Gemini returns multi-line fields as lists of lines; tests pass plain strings for brevity."""
    lines = lambda v: v.split('\n') if v else []
    return json.dumps({
        'instructions': lines(instructions), 'instructions_english': lines(instructions_english),
        'heading': '', 'heading_english': '', 'content': lines(content), 'content_english': [], **extra,
    })


TASK = {'spanish': '¿Debe prohibirse X en las escuelas?', 'english': 'Should X be banned in schools?'}

ESSAY_JSON = json.dumps({
    'word_count': 999,                      # deliberately wrong — we count locally
    'score_task_completion': 3,
    'score_topic_development': 2,
    'score_language_use': 2,
    'feedback': 'Good work.',
    'feedback_spanish': 'Buen trabajo.',
    'reasoning': 'Because.',
    'reasoning_spanish': 'Porque.',
    'confidence_task_completion': 0.9,
    'confidence_topic_development': 5.0,    # out of range — must be clamped
    'confidence_language_use': -0.3,        # out of range — must be clamped
    'overall_confidence': 0.8,
})


def audio_json(**overrides):
    payload = {
        'transcription': 'Hola, me llamo Ana.',
        'transcription_english': 'Hello, my name is Ana.',
        'score_task_completion': 3,
        'score_topic_development': 3,
        'score_language_use': 3,
        'score_fluency': 2,
        'score_coherency': 2,
        'feedback': 'Nice.',
        'feedback_spanish': 'Bien.',
        'confidence_task_completion': 0.9,
        'confidence_topic_development': 0.9,
        'confidence_language_use': 0.9,
        'confidence_fluency': 0.9,
        'confidence_coherency': 0.9,
        'overall_confidence': 0.9,
        'reasoning': 'r',
    }
    payload.update(overrides)
    return json.dumps(payload)


ESSAY_RESULT = {
    'word_count': 80,
    'scores': {'task_completion': 2, 'topic_development': 2, 'language_use': 3},
    'feedback': 'ok', 'feedback_spanish': 'bien',
    'confidence_scores': {'task_completion': 0.9, 'topic_development': 0.9, 'language_use': 0.9},
    'overall_confidence': 0.9, 'reasoning': 'r', 'reasoning_spanish': 'r',
}

AUDIO_RESULT = {
    'transcription': 'Hola.',
    'transcription_english': 'Hello.',
    'scores': {'task_completion': 2, 'topic_development': 2, 'language_use': 2, 'fluency': 2, 'coherency': 2},
    'feedback': 'ok', 'feedback_spanish': 'bien',
    'confidence_scores': {},
    'overall_confidence': 0.8, 'reasoning': 'r',
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class HelperTests(TestCase):

    def test_lu_cap_applies_only_when_language_use_is_one(self):
        capped = gs.apply_lu_cap({'task_completion': 3, 'topic_development': 3, 'language_use': 1, 'fluency': 3})
        self.assertEqual(capped['task_completion'], 2)
        self.assertEqual(capped['topic_development'], 2)
        self.assertEqual(capped['fluency'], 3)  # other dimensions untouched

    def test_lu_cap_leaves_higher_language_use_alone(self):
        for lu in (0, 2, 3):
            scores = gs.apply_lu_cap({'task_completion': 3, 'topic_development': 3, 'language_use': lu})
            self.assertEqual(scores['task_completion'], 3, f'language_use={lu}')

    def test_lu_cap_never_raises_a_low_score(self):
        scores = gs.apply_lu_cap({'task_completion': 0, 'topic_development': 1, 'language_use': 1})
        self.assertEqual(scores['task_completion'], 0)
        self.assertEqual(scores['topic_development'], 1)

    def test_confidence_is_clamped_to_a_percentage(self):
        self.assertEqual(gs.clamp_confidence(5.0), 1.0)   # Gemini has returned 5.0
        self.assertEqual(gs.clamp_confidence(-0.2), 0.0)
        self.assertEqual(gs.clamp_confidence(0.85), 0.85)


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

class PromptGenerationTests(TestCase):

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()

    def _generate_returning(self, **fields):
        return patch.object(
            self.service, '_generate',
            return_value=SimpleNamespace(text=task_json(**fields))
        )

    def test_returns_spanish_and_english(self):
        with self._generate_returning():
            task = self.service.generate_task('essay', 'B1')
        self.assertEqual(task['spanish'], 'Pregunta nueva')
        self.assertEqual(task['english'], 'New question')

    def test_instructions_come_before_the_labelled_material(self):
        with self._generate_returning(instructions='Responde.', heading='Memorándum', content='A: Maestra'):
            task = self.service.generate_task('essay', 'B1', 'correspondence')
        self.assertEqual(task['spanish'], 'Responde.\n\nMemorándum\nA: Maestra')
        self.assertEqual(task['heading'], 'Memorándum')

    def test_markdown_is_stripped_from_every_field(self):
        with self._generate_returning(instructions='**Escribe** una carta', content='# Asunto\n> **Hola**'):
            task = self.service.generate_task('essay', 'B1')
        self.assertEqual(task['instructions'], 'Escribe una carta')
        self.assertEqual(task['content'], 'Asunto\nHola')
        self.assertNotIn('*', task['spanish'])

    def test_literal_backslash_n_becomes_a_line_break(self):
        with self._generate_returning(content='De: Ana\\nPara: Maestra'):
            task = self.service.generate_task('essay', 'B1', 'correspondence')
        self.assertEqual(task['content'], 'De: Ana\nPara: Maestra')

    def test_essay_prompt_asks_for_advantages_and_disadvantages(self):
        with self._generate_returning() as gen:
            self.service.generate_task('essay', 'B1')
        instruction = gen.call_args.args[0]
        self.assertIn('two advantages and two disadvantages', instruction)
        self.assertIn('dos ventajas', instruction)

    def test_audio_prompt_asks_for_a_speakable_topic(self):
        with self._generate_returning() as gen:
            self.service.generate_task('audio', 'B1')
        instruction = gen.call_args.args[0]
        self.assertIn('50-120 seconds', instruction)
        self.assertNotIn('two advantages', instruction)

    def test_level_guidance_is_included_per_level(self):
        for level, marker in [('A1', 'Very simple'), ('B2', 'Abstract or civic')]:
            with self._generate_returning() as gen:
                self.service.generate_task('essay', level)
            instruction = gen.call_args.args[0]
            self.assertIn(f'CEFR level {level}', instruction)
            self.assertIn(marker, instruction)

    def test_unknown_level_falls_back_to_b1_guidance(self):
        with self._generate_returning() as gen:
            self.service.generate_task('essay', 'C2')
        self.assertIn(gs.LEVEL_GUIDANCE['B1'], gen.call_args.args[0])

    def test_generation_uses_high_temperature_for_variety(self):
        with self._generate_returning() as gen:
            self.service.generate_task('essay', 'B1')
        self.assertEqual(gen.call_args.kwargs['temperature'], 1.0)

    def test_falls_back_to_fixed_tasks_without_an_api_key(self):
        self.service.client = None
        self.assertEqual(self.service.generate_task('essay'), gs.DEFAULT_ESSAY_TASK)
        self.assertEqual(self.service.generate_task('audio'), gs.DEFAULT_ORAL_TASK)


# ---------------------------------------------------------------------------
# Grading prompt assembly
# ---------------------------------------------------------------------------

class PromptBuilderTests(TestCase):

    def setUp(self):
        self.service = gs.AIGradingService()

    def test_essay_prompt_carries_the_generated_task_not_the_default(self):
        prompt = self.service._build_essay_prompt('Hola mundo.', TASK)
        self.assertIn(TASK['spanish'], prompt)
        self.assertIn(TASK['english'], prompt)
        self.assertNotIn(gs.DEFAULT_ESSAY_TASK['spanish'], prompt)

    def test_audio_prompt_carries_the_generated_task_not_the_default(self):
        prompt = self.service._build_audio_prompt(TASK)
        self.assertIn(TASK['spanish'], prompt)
        self.assertNotIn(gs.DEFAULT_ORAL_TASK['spanish'], prompt)

    def test_prompts_warn_that_reference_examples_are_off_topic(self):
        # The calibration anchors still mention uniforms/travel; the rater must
        # read them as severity anchors, not as topic requirements.
        for prompt in (self.service._build_essay_prompt('Hola.', TASK), self.service._build_audio_prompt(TASK)):
            self.assertIn('written for a different task', prompt)

    def test_scoring_rules_no_longer_demand_the_old_topics(self):
        essay = self.service._build_essay_prompt('Hola.', TASK)
        self.assertIn('answering the question in the TASK PROMPT', essay)
        audio = self.service._build_audio_prompt(TASK)
        self.assertNotIn('travel prompt', audio)

    def test_essay_prompt_states_the_word_count(self):
        self.assertIn('~3 words', self.service._build_essay_prompt('uno dos tres', TASK))

    def test_audio_prompt_includes_the_rubric_criteria(self):
        prompt = self.service._build_audio_prompt(TASK)
        self.assertIn('Simulated Conversation', prompt)
        self.assertIn('Score 3 (High)', prompt)

    def test_essay_prompt_caps_topic_development_on_missing_transitions(self):
        prompt = self.service._build_essay_prompt('Hola.', TASK)
        self.assertIn('TRANSITION-WORD PENALTY', prompt)
        # The cap belongs to Topic Development, not Language Use.
        td = prompt.split('── TOPIC DEVELOPMENT ──')[1].split('── LANGUAGE USE ──')[0]
        self.assertIn('TRANSITION-WORD PENALTY', td)
        self.assertIn('TD CANNOT exceed 2', td)
        self.assertIn('TD CANNOT exceed 1', td)
        # "y"/"pero"/"también" must not count towards the transition tally.
        self.assertIn('NOT qualifying', td)


# ---------------------------------------------------------------------------
# Grading service
# ---------------------------------------------------------------------------

class EssayGradingServiceTests(TestCase):

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()

    def grade(self, essay='una dos tres cuatro', task=TASK):
        with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=ESSAY_JSON)) as gen:
            self.gen = gen
            return self.service.grade_essay(essay, task)

    def test_scores_are_returned_per_dimension(self):
        result = self.grade()
        self.assertEqual(result['scores'],
                         {'task_completion': 3, 'topic_development': 2, 'language_use': 2})

    def test_word_count_is_counted_locally_not_taken_from_gemini(self):
        self.assertEqual(self.grade('una dos tres cuatro')['word_count'], 4)

    def test_out_of_range_confidences_are_clamped(self):
        result = self.grade()
        self.assertEqual(result['confidence_scores']['topic_development'], 1.0)
        self.assertEqual(result['confidence_scores']['language_use'], 0.0)

    def test_bilingual_feedback_is_returned(self):
        result = self.grade()
        self.assertEqual(result['feedback'], 'Good work.')
        self.assertEqual(result['feedback_spanish'], 'Buen trabajo.')
        self.assertEqual(result['reasoning_spanish'], 'Porque.')

    def test_missing_task_falls_back_to_the_default_prompt(self):
        self.grade(task=None)
        self.assertIn(gs.DEFAULT_ESSAY_TASK['spanish'], self.gen.call_args.args[0])

    def test_no_api_key_raises_a_clear_error(self):
        self.service.client = None
        with self.assertRaisesMessage(ValueError, 'Gemini API key not configured'):
            self.service.grade_essay('hola', TASK)


class AudioGradingServiceTests(TestCase):

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()
        self.service.client.files.upload.return_value = SimpleNamespace(name='files/abc')

    def grade(self, path='/tmp/clip.webm', text=None, task=TASK):
        with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=text or audio_json())) as gen:
            self.gen = gen
            return self.service.grade_audio(path, task)

    def test_transcription_and_three_dimensions_are_returned(self):
        result = self.grade()
        self.assertEqual(result['transcription'], 'Hola, me llamo Ana.')
        self.assertEqual(result['transcription_english'], 'Hello, my name is Ana.')
        self.assertEqual(sorted(result['scores']),
                         ['language_use', 'task_completion', 'topic_development'])

    def test_weak_language_use_caps_the_other_dimensions(self):
        result = self.grade(text=audio_json(score_language_use=1))
        self.assertEqual(result['scores']['task_completion'], 2)
        self.assertEqual(result['scores']['topic_development'], 2)

    def test_mime_type_follows_the_file_extension(self):
        for suffix, mime in [('.mp3', 'audio/mpeg'), ('.wav', 'audio/wav'), ('.webm', 'audio/webm')]:
            self.grade(path=f'/tmp/clip{suffix}')
            self.assertEqual(self.service.client.files.upload.call_args.kwargs['config'].mime_type, mime)

    def test_unknown_extension_defaults_to_mp4(self):
        self.grade(path='/tmp/clip.aiff')
        self.assertEqual(self.service.client.files.upload.call_args.kwargs['config'].mime_type, 'audio/mp4')

    def test_uploaded_file_is_deleted_after_grading(self):
        self.grade()
        self.service.client.files.delete.assert_called_once_with(name='files/abc')

    def test_uploaded_file_is_deleted_even_when_grading_fails(self):
        with patch.object(self.service, '_generate', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.service.grade_audio('/tmp/clip.webm', TASK)
        self.service.client.files.delete.assert_called_once_with(name='files/abc')

    def test_feedback_missing_sections_is_regenerated(self):
        partial = audio_json(feedback='Task Completion:\n- ok', feedback_spanish='Cumplimiento de la tarea:\n- bien')
        full = audio_json(
            feedback='Task Completion:\n- a\nTopic Development:\n- b\nLanguage Use:\n- c',
            feedback_spanish='Cumplimiento de la tarea:\n- a\nDesarrollo del tema:\n- b\nUso del lenguaje:\n- c',
        )
        with patch.object(self.service, '_generate', side_effect=[SimpleNamespace(text=partial), SimpleNamespace(text=full)]) as gen:
            result = self.service.grade_audio('/tmp/clip.webm', TASK)
        self.assertEqual(gen.call_count, 2)
        self.assertIn('Language Use:', result['feedback'])

    def test_incomplete_feedback_still_returns_after_max_attempts(self):
        result = self.grade()   # fixture feedback has no section headings at all
        self.assertEqual(self.gen.call_count, gs.FEEDBACK_ATTEMPTS)
        self.assertEqual(result['feedback'], 'Nice.')

    def test_no_api_key_raises_before_uploading(self):
        self.service.client = None
        with self.assertRaisesMessage(ValueError, 'Gemini API key not configured'):
            self.service.grade_audio('/tmp/clip.webm', TASK)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class PromptEndpointTests(TestCase):

    def setUp(self):
        refill = patch('spanish.prompt_pool.refill_async')
        self.refill = refill.start()
        self.addCleanup(refill.stop)

    def test_passes_kind_and_level_through(self):
        task = {'spanish': 'pregunta', 'english': 'question'}
        with patch('spanish.grading_service.service.generate_task', return_value=task) as gen:
            res = self.client.post('/api/grade/prompt/', {'kind': 'audio', 'level': 'A2'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), task)
        self.assertEqual(gen.call_args.args, ('audio', 'A2', 'opinion', None))

    def test_defaults_to_an_essay_at_b1(self):
        with patch('spanish.grading_service.service.generate_task', return_value=TASK) as gen:
            self.client.post('/api/grade/prompt/', {})
        self.assertEqual(gen.call_args.args, ('essay', 'B1', 'opinion'))

    def test_serves_and_removes_a_pooled_prompt(self):
        PromptPool.objects.create(kind='essay', task_type='correspondence', level='B1', task=TASK)
        with patch('spanish.grading_service.service.generate_task') as gen:
            res = self.client.post('/api/grade/prompt/', {'kind': 'essay', 'essay_type': 'correspondence'})
        self.assertEqual(res.json(), TASK)
        gen.assert_not_called()
        self.assertFalse(PromptPool.objects.exists())
        self.refill.assert_called_once_with('essay', 'correspondence', 'B1')

    def test_pool_is_keyed_by_oral_type_and_level(self):
        PromptPool.objects.create(kind='audio', task_type='qa', level='A1', task=TASK)
        with patch('spanish.grading_service.service.generate_task', return_value={'spanish': 'live'}):
            other = self.client.post('/api/grade/prompt/', {'kind': 'audio', 'oral_type': 'situation', 'level': 'A1'})
            pooled = self.client.post('/api/grade/prompt/', {'kind': 'audio', 'oral_type': 'qa', 'level': 'A1'})
        self.assertEqual(other.json(), {'spanish': 'live'})
        self.assertEqual(pooled.json(), TASK)

    def test_refill_tops_the_pool_up_to_size(self):
        PromptPool.objects.create(kind='essay', task_type='opinion', level='B1', task=TASK)
        with patch('spanish.grading_service.service.generate_task', return_value=TASK) as gen:
            prompt_pool.refill('essay', 'opinion', 'B1')
        self.assertEqual(gen.call_count, prompt_pool.POOL_SIZE - 1)
        self.assertEqual(PromptPool.objects.count(), prompt_pool.POOL_SIZE)

    def test_a_failed_generation_is_skipped_not_fatal(self):
        results = iter([RuntimeError('429'), TASK, TASK])
        def flaky(*args):
            r = next(results, TASK)
            if isinstance(r, Exception):
                raise r
            return r
        with patch.object(prompt_pool, 'POOL_SIZE', 3), \
             patch('spanish.grading_service.service.generate_task', side_effect=flaky):
            prompt_pool.refill('essay', 'opinion', 'B1')
        self.assertEqual(PromptPool.objects.count(), 2)

    def test_prefill_also_fills_graded_speaking(self):
        from django.core.management import call_command
        with patch('spanish.management.commands.prefill_prompts.refill') as refill:
            call_command('prefill_prompts', stdout=open(os.devnull, 'w'))
        keys = {call.args for call in refill.call_args_list}
        self.assertIn(('audio', '', 'A1'), keys)
        self.assertNotIn(('essay', 'lesson_plan', 'A1'), keys)

    def test_rejects_an_unknown_kind(self):
        res = self.client.post('/api/grade/prompt/', {'kind': 'video', 'level': 'A2'})
        self.assertEqual(res.status_code, 400)

    def test_reports_generation_failure(self):
        with patch('spanish.grading_service.service.generate_task', side_effect=RuntimeError('quota')):
            res = self.client.post('/api/grade/prompt/', {'kind': 'essay'})
        self.assertEqual(res.status_code, 500)
        self.assertIn('quota', res.json()['error'])


class EssayEndpointTests(TestCase):

    def post(self, **extra):
        data = {'essay': 'hola mundo', 'session_id': 's1'}
        data.update(extra)
        with patch('spanish.grading_service.service.grade_essay', return_value=ESSAY_RESULT) as grade:
            self.grade = grade
            return self.client.post('/api/grade/essay/', data)

    def test_grades_against_the_prompt_the_student_saw(self):
        res = self.post(task_spanish=TASK['spanish'], task_english=TASK['english'])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.grade.call_args.args[1], TASK)

    def test_submission_stores_the_task_and_total_score(self):
        self.post(task_spanish=TASK['spanish'], task_english=TASK['english'])
        sub = Submission.objects.get(session_id='s1')
        self.assertEqual(sub.kind, 'essay')
        self.assertEqual(sub.total_score, 7)          # 2 + 2 + 3
        self.assertEqual(sub.task['spanish'], TASK['spanish'])
        self.assertEqual(sub.text, 'hola mundo')

    def test_without_a_task_the_rater_uses_its_default(self):
        self.post()
        self.assertIsNone(self.grade.call_args.args[1])

    def test_empty_essay_is_rejected_and_nothing_is_saved(self):
        res = self.client.post('/api/grade/essay/', {'essay': '   ', 'session_id': 's1'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Submission.objects.exists())

    def test_grading_failure_is_reported_and_nothing_is_saved(self):
        with patch('spanish.grading_service.service.grade_essay', side_effect=RuntimeError('boom')):
            res = self.client.post('/api/grade/essay/', {'essay': 'hola', 'session_id': 's1'})
        self.assertEqual(res.status_code, 500)
        self.assertFalse(Submission.objects.exists())


class AudioEndpointTests(TestCase):

    def clip(self, name='clip.webm', size=10):
        return SimpleUploadedFile(name, b'x' * size, content_type='audio/webm')

    def test_recording_is_graded_and_the_transcription_saved(self):
        with patch('spanish.grading_service.service.grade_audio', return_value=AUDIO_RESULT):
            res = self.client.post('/api/grade/audio/', {
                'audio': self.clip(), 'session_id': 's1', 'task_spanish': TASK['spanish'],
            })
        self.assertEqual(res.status_code, 200)
        sub = Submission.objects.get(session_id='s1')
        self.assertEqual(sub.kind, 'audio')
        self.assertEqual(sub.text, 'Hola.')           # transcription, not the audio
        self.assertEqual(sub.total_score, 10)         # five dimensions

    def test_missing_file_is_rejected(self):
        res = self.client.post('/api/grade/audio/', {'session_id': 's1'})
        self.assertEqual(res.status_code, 400)

    def test_unsupported_extension_is_rejected(self):
        res = self.client.post('/api/grade/audio/', {'audio': self.clip('clip.txt'), 'session_id': 's1'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Submission.objects.exists())

    def test_oversized_file_is_rejected(self):
        big = SimpleUploadedFile('clip.webm', b'x' * (26 * 1024 * 1024), content_type='audio/webm')
        res = self.client.post('/api/grade/audio/', {'audio': big, 'session_id': 's1'})
        self.assertEqual(res.status_code, 400)

    def test_temp_file_is_removed_after_grading(self):
        seen = {}

        def capture(path, task):
            seen['path'] = path
            self.assertTrue(os.path.exists(path))     # exists while grading
            return AUDIO_RESULT

        with patch('spanish.grading_service.service.grade_audio', side_effect=capture):
            self.client.post('/api/grade/audio/', {'audio': self.clip(), 'session_id': 's1'})
        self.assertFalse(os.path.exists(seen['path']))

    def test_temp_file_is_removed_when_grading_fails(self):
        seen = {}

        def blow_up(path, task):
            seen['path'] = path
            raise RuntimeError('boom')

        with patch('spanish.grading_service.service.grade_audio', side_effect=blow_up):
            res = self.client.post('/api/grade/audio/', {'audio': self.clip(), 'session_id': 's1'})
        self.assertEqual(res.status_code, 500)
        self.assertFalse(os.path.exists(seen['path']))
        self.assertFalse(Submission.objects.exists())


class HistoryEndpointTests(TestCase):

    def make(self, session_id, n=1, kind='essay'):
        for _ in range(n):
            Submission.objects.create(
                session_id=session_id, kind=kind, task=TASK, text='hola',
                result=ESSAY_RESULT, total_score=7,
            )

    def test_returns_only_the_students_own_submissions(self):
        self.make('s1', 2)
        self.make('other', 3)
        res = self.client.get('/api/grade/history/', {'session_id': 's1'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['submissions']), 2)

    def test_each_row_carries_the_prompt_it_was_graded_against(self):
        self.make('s1')
        row = self.client.get('/api/grade/history/', {'session_id': 's1'}).json()['submissions'][0]
        self.assertEqual(row['task']['spanish'], TASK['spanish'])
        self.assertEqual(row['total_score'], 7)
        self.assertIn('created_at', row)

    def test_history_can_be_scoped_to_one_kind(self):
        self.make('s1', 2, kind='essay')
        self.make('s1', 3, kind='audio')
        essays = self.client.get('/api/grade/history/', {'session_id': 's1', 'kind': 'essay'}).json()
        self.assertEqual(len(essays['submissions']), 2)
        recordings = self.client.get('/api/grade/history/', {'session_id': 's1', 'kind': 'audio'}).json()
        self.assertEqual(len(recordings['submissions']), 3)

    def test_history_without_a_kind_returns_both(self):
        self.make('s1', 2, kind='essay')
        self.make('s1', 1, kind='audio')
        res = self.client.get('/api/grade/history/', {'session_id': 's1'})
        self.assertEqual(len(res.json()['submissions']), 3)

    def test_history_is_capped_at_twenty(self):
        self.make('s1', 22)
        res = self.client.get('/api/grade/history/', {'session_id': 's1'})
        self.assertEqual(len(res.json()['submissions']), 20)

    def test_empty_history_is_not_an_error(self):
        res = self.client.get('/api/grade/history/', {'session_id': 'nobody'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['submissions'], [])


class EssayTypeTests(TestCase):
    """The BTLPT written-task type picks the Task Completion / Topic Development rules."""

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()

    def _prompt(self, essay_type):
        return self.service._build_essay_prompt('una dos tres', TASK, essay_type)

    def test_opinion_prompt_demands_advantages_and_disadvantages(self):
        prompt = self._prompt('opinion')
        self.assertIn('2 distinct advantages', prompt)
        self.assertNotIn('greeting', prompt)

    def test_correspondence_prompt_demands_correspondence_form(self):
        prompt = self._prompt('correspondence')
        self.assertIn('letter, memo or email', prompt)
        self.assertIn('greeting', prompt)
        self.assertNotIn('2 distinct advantages', prompt)

    def test_unknown_type_falls_back_to_the_opinion_essay(self):
        self.assertEqual(self._prompt('nonsense'), self._prompt('opinion'))

    def test_generated_task_follows_the_selected_type(self):
        with patch.object(
            self.service, '_generate',
            return_value=SimpleNamespace(text=task_json())
        ) as gen:
            self.service.generate_task('essay', 'B1', 'correspondence')
        instruction = gen.call_args.args[0]
        for marker in ('parent', 'principal', 'PTO president', 'invent a realistic full name'):
            self.assertIn(marker, instruction)

    def test_correspondence_greeting_uses_a_colon(self):
        with patch.object(
            self.service, '_generate',
            return_value=SimpleNamespace(text=task_json())
        ) as gen:
            self.service.generate_task('essay', 'B1', 'correspondence')
        instruction = gen.call_args.args[0]
        self.assertIn('COLON, never a comma', instruction)
        self.assertIn('Estimada Sra. Morales:', instruction)

    def test_oral_tasks_with_a_listener_name_that_person(self):
        for oral_type in ('conversation', 'qa', 'situation'):
            with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=task_json())) as gen:
                self.service.generate_task('audio', 'B1', oral_type=oral_type)
            self.assertIn('invented, realistic full name', gen.call_args.args[0])
        with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=task_json())) as gen:
            self.service.generate_task('audio', 'B1', oral_type='presentation')
        self.assertNotIn('invented, realistic full name', gen.call_args.args[0])

    def test_correspondence_content_gets_letter_spacing(self):
        memo = ('A: Maestra de quinto grado\nDe: Elena Flores\nAsunto: Jardín\nEstimada maestra:\n'
                'Primer párrafo.\nSegundo párrafo.\nAtentamente,\nElena Flores\nPresidenta de la APT')
        with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=task_json(content=memo))):
            task = self.service.generate_task('essay', 'B1', 'correspondence')
        self.assertEqual(task['content'], (
            'A: Maestra de quinto grado\nDe: Elena Flores\nAsunto: Jardín\n\nEstimada maestra:\n\n'
            'Primer párrafo.\n\nSegundo párrafo.\n\nAtentamente,\n\nElena Flores\nPresidenta de la APT'))

    def test_correspondence_format_is_chosen_by_code_not_the_model(self):
        for fmt, marker in zip(gs.CORRESPONDENCE_FORMATS, ('an email', 'a memo', 'a letter')):
            with patch.object(gs.random, 'choice', return_value=fmt), patch.object(
                self.service, '_generate', return_value=SimpleNamespace(text=task_json())
            ) as gen:
                self.service.generate_task('essay', 'B1', 'correspondence')
            instruction = gen.call_args.args[0]
            self.assertIn(f'Format: {marker}', instruction)
            self.assertNotIn('{', instruction.split('Level B1 guidance')[0])

    def test_lesson_plan_grade_is_chosen_by_code_not_tied_to_level(self):
        with patch.object(gs.random, 'choice', return_value='Grade 4'), patch.object(
            self.service, '_generate', return_value=SimpleNamespace(text=task_json())
        ) as gen:
            self.service.generate_task('essay', 'A2', 'lesson_plan')
        instruction = gen.call_args.args[0]
        self.assertIn('The grade is Grade 4', instruction)
        self.assertNotIn('{grade}', instruction)

    def test_lesson_plan_task_is_teks_aligned_and_k_to_5(self):
        with patch.object(
            self.service, '_generate',
            return_value=SimpleNamespace(text=task_json())
        ) as gen:
            self.service.generate_task('essay', 'B1', 'lesson_plan')
        instruction = gen.call_args.args[0]
        for marker in ('TEKS', 'Kindergarten through Grade 5', '§128.7', '§113.16'):
            self.assertIn(marker, instruction)

    def test_feedback_is_requested_per_dimension_with_the_reason_last(self):
        for prompt in (self._prompt('opinion'), self.service._build_audio_prompt(TASK)):
            self.assertIn('Task Completion:', prompt)
            self.assertIn('Language Use:', prompt)
            self.assertIn("LAST bullet", prompt)
            self.assertIn("rater's reason", prompt)

    def test_audio_feedback_covers_the_three_btlpt_dimensions(self):
        prompt = self.service._build_audio_prompt(TASK)
        for heading in ('Task Completion:', 'Topic Development:', 'Language Use:'):
            self.assertIn(heading, prompt)
        for heading in ('Fluency:', 'Coherency:'):
            self.assertNotIn(heading, prompt)


# ---------------------------------------------------------------------------
# Chat grammar correction
# ---------------------------------------------------------------------------

class ChatCorrectionTests(TestCase):
    """The correction is its own Gemini call on the student's latest message, every turn."""

    def _correct(self, text, model_says):
        from . import gemini_service
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({'correction': model_says}))
        with patch.object(gemini_service.genai, 'Client', return_value=client):
            return gemini_service.correct_message(text)

    def test_missing_opening_question_mark_is_added_even_if_the_model_misses_it(self):
        self.assertEqual(self._correct('Me puedes compartir más?', ''), '¿Me puedes compartir más?')
        self.assertEqual(self._correct('Cuáles son las razones?', 'Cuáles son las razones?'), '¿Cuáles son las razones?')

    def test_correct_message_gets_no_correction(self):
        self.assertEqual(self._correct('¿Qué es LPAC?', ''), '')
        self.assertEqual(self._correct('¿Qué es LPAC?', '¿Qué es LPAC?'), '')

    def test_english_message_is_left_alone(self):
        self.assertEqual(self._correct('What is LPAC?', ''), '')

    def test_every_turn_is_corrected_not_just_the_first(self):
        from . import gemini_service
        thread = [
            {'role': 'model', 'parts': ['¡Hola!']},
            {'role': 'user', 'parts': ['Que es LPAC?']},
            {'role': 'model', 'parts': ['Es un comité.']},
            {'role': 'user', 'parts': ['Me puedes compartir más?']},
        ]
        with patch.object(gemini_service, '_chat_reply', return_value='Claro.'), \
             patch.object(gemini_service, 'correct_message', return_value='¿Me puedes compartir más?') as fix:
            result = gemini_service.chat(thread, 'B1', 'LPAC')
        fix.assert_called_once_with('Me puedes compartir más?')
        self.assertEqual(result, {'reply': 'Claro.', 'correction': '¿Me puedes compartir más?'})

    def test_a_failed_correction_still_returns_the_reply(self):
        from . import gemini_service
        with patch.object(gemini_service, '_chat_reply', return_value='Claro.'), \
             patch.object(gemini_service, 'correct_message', side_effect=RuntimeError('boom')):
            result = gemini_service.chat([{'role': 'user', 'parts': ['hola']}], 'B1')
        self.assertEqual(result, {'reply': 'Claro.', 'correction': ''})


class SchoolContextTests(TestCase):
    """Every generated task is steered toward school settings."""

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()

    def test_every_task_kind_carries_the_school_context_rule(self):
        calls = [('essay', 'opinion', None), ('essay', 'correspondence', None), ('essay', 'lesson_plan', None),
                 ('audio', 'opinion', None), ('audio', 'opinion', 'conversation'), ('audio', 'opinion', 'situation')]
        for kind, essay_type, oral_type in calls:
            with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=task_json())) as gen:
                self.service.generate_task(kind, 'B1', essay_type, oral_type)
            self.assertIn(gs.SCHOOL_CONTEXT_RULE, gen.call_args.args[0], (kind, essay_type, oral_type))
            self.assertIn('grocery store', gen.call_args.args[0])
            self.assertIn(gs.TEACHER_ROLE_RULE, gen.call_args.args[0])
            self.assertIn('NOT a K-12 student', gen.call_args.args[0])


# ---------------------------------------------------------------------------
# Turn-by-turn Simulated Conversation
# ---------------------------------------------------------------------------

CONVERSATION_TASK = {
    'spanish': 'Escenario: Hablas con la Sra. Gómez.\n\nTurno 1: ¿Hola?\nTurno 2: ¿Por qué?\nTurno 3: ¿Y luego?\nTurno 4: Adiós.',
    'english': '',
}


def conversation_json(**overrides):
    payload = {
        'transcription_turn_1': 'Buenos días, Sra. Gómez.', 'transcription_turn_2': 'Porque me gusta.',
        'transcription_turn_3': 'Luego trabajo.', 'transcription_turn_4': 'Hasta luego.',
        'transcription_english': 'Turn 1: Good morning.',
        'score_task_completion': 3, 'score_topic_development': 2, 'score_language_use': 2,
        'feedback': 'Task Completion:\n- a\nTopic Development:\n- b\nLanguage Use:\n- c',
        'feedback_spanish': 'Cumplimiento de la tarea:\n- a\nDesarrollo del tema:\n- b\nUso del lenguaje:\n- c',
        'confidence_task_completion': 0.9, 'confidence_topic_development': 0.9,
        'confidence_language_use': 0.9, 'overall_confidence': 0.9, 'reasoning': 'r',
    }
    payload.update(overrides)
    return json.dumps(payload)


class ConversationGradingTests(TestCase):

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()
        self.service.client.files.upload.side_effect = [SimpleNamespace(name=f'files/{i}') for i in range(1, 5)]

    def grade(self, text=None):
        paths = [f'/tmp/turn-{i}.webm' for i in range(1, 5)]
        with patch.object(self.service, '_generate', return_value=SimpleNamespace(text=text or conversation_json())) as gen:
            self.gen = gen
            return self.service.grade_conversation(paths, CONVERSATION_TASK)

    def test_each_clip_is_labelled_with_its_turn_and_all_are_deleted(self):
        self.grade()
        contents = self.gen.call_args.args[0]
        self.assertEqual(contents[0], 'Answer to Turno 1:')
        self.assertEqual(contents[6], 'Answer to Turno 4:')
        self.assertEqual(self.service.client.files.delete.call_count, 4)

    def test_per_turn_transcriptions_are_returned_and_joined(self):
        result = self.grade()
        self.assertEqual(result['turn_transcriptions'][3], 'Hasta luego.')
        self.assertIn('Turno 2: Porque me gusta.', result['transcription'])

    def test_prompt_drops_the_long_recording_length_rules(self):
        prompt = self.service._build_conversation_prompt(CONVERSATION_TASK)
        self.assertIn('NEVER penalize an answer for ending mid-sentence', prompt)
        self.assertNotIn('60–90 seconds', prompt)
        self.assertIn('── LANGUAGE USE ──', prompt)

    def test_weak_language_use_still_caps_the_other_scores(self):
        result = self.grade(conversation_json(score_language_use=1))
        self.assertEqual(result['scores']['task_completion'], 2)


class ConversationEndpointTests(TestCase):

    def _post(self, files):
        data = {'oral_type': 'conversation', 'task_spanish': CONVERSATION_TASK['spanish'], **files}
        return self.client.post('/api/grade/audio/', data)

    def test_four_turn_clips_are_graded_as_a_conversation(self):
        files = {f'audio_{i}': SimpleUploadedFile(f'turn-{i}.webm', b'x', content_type='audio/webm') for i in range(1, 5)}
        fake = {**AUDIO_RESULT, 'transcription': 'Turno 1: Hola.', 'turn_transcriptions': ['Hola.', '', '', '']}
        with patch('spanish.grading_service.service.grade_conversation', return_value=fake) as grade:
            res = self._post(files)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(grade.call_args.args[0]), 4)
        self.assertEqual(Submission.objects.get().text, 'Turno 1: Hola.')

    def test_a_missing_turn_clip_is_rejected(self):
        files = {f'audio_{i}': SimpleUploadedFile(f'turn-{i}.webm', b'x', content_type='audio/webm') for i in range(1, 4)}
        res = self._post(files)
        self.assertEqual(res.status_code, 400)

    def test_a_single_recording_conversation_still_uses_the_general_grader(self):
        upload = SimpleUploadedFile('clip.webm', b'x', content_type='audio/webm')
        with patch('spanish.grading_service.service.grade_audio', return_value=AUDIO_RESULT) as grade:
            res = self.client.post('/api/grade/audio/', {'oral_type': 'conversation', 'audio': upload})
        self.assertEqual(res.status_code, 200)
        grade.assert_called_once()



class GraderRetryTests(TestCase):
    """A cut-off (looping) grader reply is retried, not shown to the student as a crash."""

    def setUp(self):
        self.service = gs.AIGradingService()
        self.service.client = MagicMock()
        self.service.client.files.upload.side_effect = [SimpleNamespace(name=f'files/{i}') for i in range(1, 5)]

    def test_cut_off_json_from_a_transcription_loop_is_retried(self):
        looping = '{\n "transcription_turn_1": "Ah, sí, tengo. Ah, sí, tengo. Ah,'
        with patch.object(self.service, '_generate', side_effect=[
            SimpleNamespace(text=looping), SimpleNamespace(text=conversation_json()),
        ]) as gen:
            result = self.service.grade_conversation([f'/tmp/t{i}.webm' for i in range(1, 5)], CONVERSATION_TASK)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(gen.call_args.kwargs['temperature'], 0.6)   # retry runs warmer
        self.assertEqual(result['scores']['task_completion'], 3)

    def test_every_attempt_cut_off_gives_a_clear_error(self):
        looping = SimpleNamespace(text='{"transcription_turn_1": "Ah, sí, tengo. Ah,')
        with patch.object(self.service, '_generate', return_value=looping):
            with self.assertRaisesMessage(ValueError, 'cut off'):
                self.service.grade_conversation([f'/tmp/t{i}.webm' for i in range(1, 5)], CONVERSATION_TASK)
        self.assertEqual(self.service.client.files.delete.call_count, 4)


# ---------------------------------------------------------------------------
# Listening Comprehension
# ---------------------------------------------------------------------------

def listening_json(**overrides):
    payload = {
        'title': 'Una reunión', 'speaker_names': ['Sra. Gómez', 'Sr. Ruiz'],
        'speaker_roles': ['maestra', 'padre'], 'speaker_genders': ['female', 'male'],
        'line_speakers': ['Sra. Gómez', 'Sr. Ruiz'], 'line_texts': ['Buenos días.', 'Hola.'],
    }
    for i in range(1, 5):
        payload.update({f'question_{i}': f'¿Pregunta {i}?', f'options_{i}': ['a', 'b', 'c', 'd'],
                        f'answer_{i}': 'b', f'explanation_{i}': 'Porque sí.',
                        f'explanation_english_{i}': 'Because.'})
    payload.update(overrides)
    return json.dumps(payload)


def tts_response(pcm=b'\x00\x00' * 240):
    part = SimpleNamespace(inline_data=SimpleNamespace(data=pcm))
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


class ListeningServiceTests(TestCase):

    def _generate(self, script_texts, selection_type='dialogue'):
        from . import listening_service as ls
        client = MagicMock()
        client.models.generate_content.side_effect = [SimpleNamespace(text=t) for t in script_texts] + [tts_response()]
        with patch.object(ls, '_client', return_value=client):
            return ls.generate_selection('B1', selection_type), client

    def test_selection_has_script_questions_and_playable_audio(self):
        import base64
        selection, _ = self._generate([listening_json()])
        self.assertEqual(len(selection['questions']), 4)
        self.assertEqual(selection['script'][0], {'speaker': 'Sra. Gómez', 'text': 'Buenos días.'})
        self.assertIn(selection['audio_mime'], ('audio/mpeg', 'audio/wav'))
        self.assertTrue(base64.b64decode(selection['audio']))

    def test_each_question_carries_a_spanish_and_english_rationale(self):
        selection, _ = self._generate([listening_json()])
        self.assertEqual(selection['questions'][0]['explanation'], 'Porque sí.')
        self.assertEqual(selection['questions'][0]['explanation_english'], 'Because.')

    def test_answer_stays_among_the_shuffled_options(self):
        selection, _ = self._generate([listening_json()])
        for q in selection['questions']:
            self.assertIn(q['answer'], q['options'])
            self.assertEqual(sorted(q['options']), ['a', 'b', 'c', 'd'])

    def test_script_prompt_names_an_elementary_school_situation(self):
        from . import listening_service as ls
        for kind, (_, _, situations) in ls.SELECTION_TYPES.items():
            prompt = ls._script_prompt('B1', kind)
            self.assertIn('ELEMENTARY school', prompt)
            self.assertTrue(any(f'Situation: {s}.' in prompt for s in situations))
        self.assertIn('LPAC meeting', ls._script_prompt('B1', 'dialogue', ls.SELECTION_TYPES['dialogue'][2][3]))

    def test_letter_labels_the_model_writes_are_stripped(self):
        labelled = listening_json(options_1=['A) Un pintor', 'B. Un artesano', '(C) Un coleccionista', 'D - Un curandero'],
                                  answer_1='B. Un artesano')
        selection, _ = self._generate([labelled])
        q = selection['questions'][0]
        self.assertEqual(sorted(q['options']), ['Un artesano', 'Un coleccionista', 'Un curandero', 'Un pintor'])
        self.assertEqual(q['answer'], 'Un artesano')

    def test_pooled_selection_with_labelled_options_is_stale(self):
        from .prompt_pool import is_current
        q = {'question': '¿?', 'answer': 'Un pintor', 'explanation_english': 'x'}
        self.assertFalse(is_current('listening', {'questions': [dict(q, options=['A) Un pintor', 'B) Otro'])]}))
        self.assertTrue(is_current('listening', {'questions': [dict(q, options=['Un pintor', 'A las tres'])]}))

    def test_a_malformed_selection_is_regenerated(self):
        bad = listening_json(answer_2='z')   # answer not among the options
        selection, client = self._generate([bad, listening_json()])
        self.assertEqual(client.models.generate_content.call_count, 3)   # bad script, good script, TTS
        self.assertEqual(selection['questions'][1]['answer'], 'b')

    def test_dialogue_gets_two_distinct_voices_with_matching_labels(self):
        _, client = self._generate([listening_json()])
        tts_call = client.models.generate_content.call_args_list[-1]
        speakers = tts_call.kwargs['config'].speech_config.multi_speaker_voice_config.speaker_voice_configs
        self.assertEqual([s.speaker for s in speakers], ['SraGomez', 'SrRuiz'])
        self.assertNotEqual(speakers[0].voice_config.prebuilt_voice_config.voice_name,
                            speakers[1].voice_config.prebuilt_voice_config.voice_name)
        self.assertIn('SraGomez: Buenos días.', tts_call.kwargs['contents'])

    def test_a_talk_has_one_speaker_and_one_voice(self):
        talk = listening_json(speaker_names=['Dra. Vega'], speaker_roles=['especialista'],
                              speaker_genders=['female'], line_speakers=['Dra. Vega'], line_texts=['Hoy hablamos.'])
        _, client = self._generate([talk], 'informational')
        config = client.models.generate_content.call_args_list[-1].kwargs['config']
        self.assertIsNotNone(config.speech_config.voice_config)

    def test_wav_fallback_when_the_mp3_encoder_is_missing(self):
        from . import listening_service as ls
        with patch.dict('sys.modules', {'lameenc': None}):
            audio, mime = ls.encode_audio(b'\x00\x00' * 100)
        self.assertEqual(mime, 'audio/wav')
        self.assertTrue(audio.startswith(b'RIFF'))


class TtsEndpointTests(TestCase):
    """Chat (Voice) and the Simulated Conversation speak with the Google voices via /api/tts/."""

    def _post(self, body):
        from . import listening_service as ls
        client = MagicMock()
        client.models.generate_content.side_effect = lambda **kw: tts_response()
        with patch.object(ls, '_client', return_value=client):
            res = self.client.post('/api/tts/', body, content_type='application/json')
        return res, client

    def test_each_text_gets_a_playable_clip_in_one_voice(self):
        import base64
        res, client = self._post({'texts': ['Turno uno.', 'Turno dos.'], 'voice': 'Charon'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['voice'], 'Charon')
        self.assertEqual(len(res.data['clips']), 2)
        self.assertTrue(base64.b64decode(res.data['clips'][0]['audio']))
        voices = {c.kwargs['config'].speech_config.voice_config.prebuilt_voice_config.voice_name
                  for c in client.models.generate_content.call_args_list}
        self.assertEqual(voices, {'Charon'})

    def test_voice_matches_the_gender_of_the_person_in_the_scenario(self):
        from . import listening_service as ls
        res, _ = self._post({'texts': ['Hola.'], 'context': 'Escenario: Hablas con el Sr. Andrés Rivera, director.'})
        self.assertIn(res.data['voice'], ls.VOICES['male'])
        res, _ = self._post({'texts': ['Hola.'], 'context': 'Escenario: Hablas con la Sra. Patricia Gómez, directora.'})
        self.assertIn(res.data['voice'], ls.VOICES['female'])

    def test_speaker_gender_reads_the_first_person_named(self):
        from .listening_service import speaker_gender
        self.assertEqual(speaker_gender('Hablas con la Dra. Ana Ruiz sobre el estudiante Mateo.'), 'female')
        self.assertEqual(speaker_gender('Tu director, el Sr. Rivera, te pregunta; salúdalo.'), 'male')
        self.assertEqual(speaker_gender('Hablas con el padre de una alumna.'), 'male')
        self.assertIsNone(speaker_gender('Hablas con tu colega sobre el proyecto.'))

    def test_unknown_voice_falls_back_to_a_google_voice(self):
        from . import listening_service as ls
        res, _ = self._post({'texts': ['Hola.'], 'voice': 'NotAVoice'})
        self.assertIn(res.data['voice'], ls.ALL_VOICES)

    def test_rejects_empty_or_too_many_texts(self):
        self.assertEqual(self._post({'texts': []})[0].status_code, 400)
        self.assertEqual(self._post({'texts': ['a'] * 7})[0].status_code, 400)
        self.assertEqual(self._post({'texts': ['  ']})[0].status_code, 400)


class ListeningEndpointTests(TestCase):

    def setUp(self):
        refill = patch('spanish.prompt_pool.refill_async')
        refill.start()
        self.addCleanup(refill.stop)

    def test_serves_a_pooled_selection_for_the_level(self):
        pooled = {'title': 'pooled', 'questions': [{'explanation': 'x', 'explanation_english': 'y'}]}
        PromptPool.objects.create(kind='listening', task_type='', level='A2', task=pooled)
        res = self.client.post('/api/listening/', {'level': 'A2'})
        self.assertEqual(res.json(), pooled)
        self.assertFalse(PromptPool.objects.exists())

    def test_a_stale_selection_without_english_rationale_is_dropped_not_served(self):
        stale = {'title': 'old', 'questions': [{'explanation': 'x'}]}
        fresh = {'title': 'new', 'questions': [{'explanation': 'x', 'explanation_english': 'y'}]}
        PromptPool.objects.create(kind='listening', task_type='', level='A1', task=stale)
        with patch('spanish.listening_service.generate_selection', return_value=fresh):
            res = self.client.post('/api/listening/', {'level': 'A1'})
        self.assertEqual(res.json()['title'], 'new')
        self.assertFalse(PromptPool.objects.exists())

    def test_generates_live_when_the_pool_is_empty(self):
        with patch('spanish.listening_service.generate_selection', return_value={'title': 'live'}) as gen:
            res = self.client.post('/api/listening/', {'level': 'B2'})
        self.assertEqual(res.json(), {'title': 'live'})
        gen.assert_called_once_with('B2')

    def test_listening_pool_is_smaller_and_prefilled(self):
        self.assertLess(prompt_pool.pool_size('listening'), prompt_pool.pool_size('essay'))
        from django.core.management import call_command
        with patch('spanish.management.commands.prefill_prompts.refill') as refill:
            call_command('prefill_prompts', stdout=open(os.devnull, 'w'))
        self.assertIn(('listening', '', 'B1'), {c.args for c in refill.call_args_list})
