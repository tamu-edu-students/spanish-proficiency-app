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
from .models import Submission


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

    def _generate_returning(self, spanish='Pregunta nueva', english='New question'):
        return patch.object(
            self.service, '_generate',
            return_value=SimpleNamespace(text=json.dumps({'spanish': spanish, 'english': english}))
        )

    def test_returns_spanish_and_english(self):
        with self._generate_returning():
            task = self.service.generate_task('essay', 'B1')
        self.assertEqual(task, {'spanish': 'Pregunta nueva', 'english': 'New question'})

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
        # The calibration anchors still mention uniforms/travel; the grader must
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

    def test_transcription_and_five_dimensions_are_returned(self):
        result = self.grade()
        self.assertEqual(result['transcription'], 'Hola, me llamo Ana.')
        self.assertEqual(result['transcription_english'], 'Hello, my name is Ana.')
        self.assertEqual(sorted(result['scores']),
                         ['coherency', 'fluency', 'language_use', 'task_completion', 'topic_development'])

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

    def test_no_api_key_raises_before_uploading(self):
        self.service.client = None
        with self.assertRaisesMessage(ValueError, 'Gemini API key not configured'):
            self.service.grade_audio('/tmp/clip.webm', TASK)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class PromptEndpointTests(TestCase):

    def test_passes_kind_and_level_through(self):
        task = {'spanish': 'pregunta', 'english': 'question'}
        with patch('spanish.grading_service.service.generate_task', return_value=task) as gen:
            res = self.client.post('/api/grade/prompt/', {'kind': 'audio', 'level': 'A2'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), task)
        self.assertEqual(gen.call_args.args, ('audio', 'A2'))

    def test_defaults_to_an_essay_at_b1(self):
        with patch('spanish.grading_service.service.generate_task', return_value=TASK) as gen:
            self.client.post('/api/grade/prompt/', {})
        self.assertEqual(gen.call_args.args, ('essay', 'B1'))

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

    def test_without_a_task_the_grader_uses_its_default(self):
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
