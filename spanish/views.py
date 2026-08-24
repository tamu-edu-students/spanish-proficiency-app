import json
import time
import random
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from . import gemini_service
from .models import UserProgress, FlashCard


def get_or_create_progress(session_id, netid=''):
    progress, created = UserProgress.objects.get_or_create(
        session_id=session_id,
        defaults={'level': 'B1', 'netid': netid}
    )
    if created:
        print(f"New user created: {session_id}")
    return progress


def get_session_id(request, fallback='default'):
    if not settings.DEV_MODE and request.user.is_authenticated:
        return str(request.user.id)
    return request.data.get('session_id', request.query_params.get('session_id', fallback))


def call_with_retry(fn, max_retries=4):
    last_error = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limited, waiting {wait:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
    raise last_error


@api_view(['GET'])
def get_current_user(request):
    if settings.DEV_MODE:
        return Response({
            'netid':      'dev_user',
            'name':       'Dev User',
            'email':      'dev@tamu.edu',
            'user_id':    'dev_001',
            'session_id': 'dev_001',
            'dev_mode':   True
        })
    if not request.user.is_authenticated:
        return Response({'error': 'Not logged in'}, status=status.HTTP_401_UNAUTHORIZED)
    return Response({
        'netid':      request.user.username,
        'name':       f"{request.user.first_name} {request.user.last_name}".strip(),
        'email':      request.user.email,
        'user_id':    str(request.user.id),
        'session_id': str(request.user.id),
        'dev_mode':   False
    })


@api_view(['POST'])
def chat_view(request):
    try:
        messages = request.data.get('messages', [])
        level    = request.data.get('level', 'B1')
        is_voice = request.data.get('session_id') == 'voice_user'

        if not messages:
            return Response({'error': 'No messages provided'}, status=status.HTTP_400_BAD_REQUEST)

        if is_voice:
            reply = call_with_retry(lambda: gemini_service.voice_chat(messages, level))
        else:
            reply = call_with_retry(lambda: gemini_service.chat(messages, level))

        return Response({'reply': reply})

    except Exception as e:
        print(f"Chat error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def flashcards_view(request):
    try:
        topic      = request.data.get('topic', 'daily life')
        level      = request.data.get('level', 'B1')
        session_id = get_session_id(request)

        raw = call_with_retry(lambda: gemini_service.generate_flashcards(topic, level))

        clean = raw.strip()
        if clean.startswith('```'):
            lines = clean.split('\n')
            clean = '\n'.join(lines[1:-1])
        clean = clean.replace('```', '').strip()

        cards = json.loads(clean)

        for card in cards:
            FlashCard.objects.get_or_create(
                session_id=session_id,
                word=card.get('word', ''),
                defaults={
                    'translation': card.get('translation', ''),
                    'example':     card.get('example', '')
                }
            )

        return Response({'cards': cards})

    except json.JSONDecodeError:
        return Response({'error': 'Could not parse flashcards. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        print(f"Flashcards error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def quiz_batch_view(request):
    try:
        level = request.data.get('level', 'B1')
        count = request.data.get('count', 10)

        raw = call_with_retry(lambda: gemini_service.generate_quiz_batch(level, count))
        print(f"Raw quiz batch response: {raw[:200]}")

        clean = raw.strip()
        if clean.startswith('```'):
            lines = clean.split('\n')
            clean = '\n'.join(lines[1:-1])
        clean = clean.replace('```', '').strip()

        questions = json.loads(clean)

        if not isinstance(questions, list):
            raise ValueError("Expected a JSON array")

        return Response({'questions': questions})

    except json.JSONDecodeError as e:
        print(f"Quiz batch JSON error: {e}")
        return Response({'error': 'Could not parse questions. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        print(f"Quiz batch error: {e}")
        import traceback; traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def quiz_view(request):
    try:
        level = request.data.get('level', 'B1')

        raw = call_with_retry(lambda: gemini_service.generate_quiz_batch(level, 1))

        clean = raw.strip()
        if clean.startswith('```'):
            lines = clean.split('\n')
            clean = '\n'.join(lines[1:-1])
        clean = clean.replace('```', '').strip()

        parsed   = json.loads(clean)
        question = parsed[0] if isinstance(parsed, list) else parsed

        return Response({'question': question})

    except Exception as e:
        print(f"Quiz error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def check_answer_view(request):
    try:
        question       = request.data.get('question', '')
        user_answer    = request.data.get('user_answer', '')
        correct_answer = request.data.get('correct_answer', '')
        level          = request.data.get('level', 'B1')

        feedback = call_with_retry(
            lambda: gemini_service.check_quiz_answer(question, user_answer, correct_answer, level)
        )
        return Response({'feedback': feedback})

    except Exception as e:
        print(f"Check answer error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def progress_view(request):
    try:
        session_id = get_session_id(request)
        progress   = get_or_create_progress(session_id)

        if 'streak'        in request.data: progress.streak        = request.data['streak']
        if 'words_learned' in request.data: progress.words_learned = request.data['words_learned']
        if 'accuracy'      in request.data: progress.accuracy      = request.data['accuracy']
        if 'level'         in request.data: progress.level         = request.data['level']
        if 'last_visit'    in request.data:
            from datetime import date
            progress.last_visit = request.data['last_visit']

        progress.save()

        level_up  = False
        old_level = progress.level

        thresholds = {
            'A1': {'words': 20,  'accuracy': 60},
            'A2': {'words': 50,  'accuracy': 65},
            'B1': {'words': 100, 'accuracy': 70},
            'B2': {'words': 200, 'accuracy': 75},
        }
        next_level = {'A1': 'A2', 'A2': 'B1', 'B1': 'B2', 'B2': 'C1'}

        current = progress.level
        if current in thresholds:
            t = thresholds[current]
            if progress.words_learned >= t['words'] and progress.accuracy >= t['accuracy']:
                progress.level = next_level[current]
                level_up = True
                progress.save()
                print(f"Level up: {old_level} to {progress.level}")

        return Response({
            'saved':     True,
            'level_up':  level_up,
            'old_level': old_level,
            'progress':  {
                'level':         progress.level,
                'streak':        progress.streak,
                'words_learned': progress.words_learned,
                'accuracy':      progress.accuracy,
            }
        })

    except Exception as e:
        print(f"Progress error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_progress_view(request):
    try:
        session_id = get_session_id(request)
        progress   = get_or_create_progress(session_id)

        return Response({
            'level':         progress.level,
            'streak':        progress.streak,
            'words_learned': progress.words_learned,
            'accuracy':      progress.accuracy,
            'last_visit':    progress.last_visit.isoformat() if progress.last_visit else None,
        })

    except Exception as e:
        print(f"Get progress error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)