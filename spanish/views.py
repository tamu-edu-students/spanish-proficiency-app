import json
import time
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from . import gemini_service
from .models import UserProgress, FlashCard, ConversationMessage


def get_or_create_progress(session_id):
    progress, _ = UserProgress.objects.get_or_create(
        session_id=session_id,
        defaults={'level': 'B1'}
    )
    return progress


def call_with_retry(fn, max_retries=3):
    """Retry up to 3 times if Gemini quota is exceeded."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                wait = (attempt + 1) * 15
                print(f"⚠ Rate limited — waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
    raise last_error


@api_view(['POST'])
def chat_view(request):
    try:
        session_id = request.data.get('session_id', 'default')
        messages   = request.data.get('messages', [])
        level      = request.data.get('level', 'B1')
        is_voice   = session_id == 'voice_user'

        if not messages:
            return Response(
                {'error': 'No messages provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        last_message = messages[-1]
        ConversationMessage.objects.create(
            session_id = session_id,
            role       = 'user',
            content    = last_message['parts'][0]
        )

        # Use faster voice-optimized function for voice sessions
        if is_voice:
            print(f"→ Voice chat request at level {level}")
            reply = call_with_retry(
                lambda: gemini_service.voice_chat(messages, level)
            )
        else:
            print(f"→ Chat request at level {level}")
            reply = call_with_retry(
                lambda: gemini_service.chat(messages, level)
            )

        ConversationMessage.objects.create(
            session_id = session_id,
            role       = 'model',
            content    = reply
        )

        return Response({'reply': reply})

    except Exception as e:
        print(f"Chat error: {e}")
        import traceback; traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def flashcards_view(request):
    try:
        topic      = request.data.get('topic', 'daily life')
        level      = request.data.get('level', 'B1')
        session_id = request.data.get('session_id', 'default')

        raw = call_with_retry(
            lambda: gemini_service.generate_flashcards(topic, level)
        )
        print(f"Raw flashcards response: {raw[:200]}")

        clean = raw.strip()
        if clean.startswith('```'):
            lines = clean.split('\n')
            clean = '\n'.join(lines[1:-1])
        clean = clean.replace('```', '').strip()

        cards = json.loads(clean)

        for card in cards:
            FlashCard.objects.get_or_create(
                session_id = session_id,
                word       = card.get('word', ''),
                defaults   = {
                    'translation': card.get('translation', ''),
                    'example':     card.get('example', '')
                }
            )

        return Response({'cards': cards})

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return Response(
            {'error': 'Could not parse flashcards. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        print(f"Flashcards error: {e}")
        import traceback; traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def quiz_view(request):
    try:
        level = request.data.get('level', 'B1')

        raw = call_with_retry(
            lambda: gemini_service.generate_quiz(level)
        )
        print(f"Raw quiz response: {raw[:200]}")

        clean = raw.strip()
        if clean.startswith('```'):
            lines = clean.split('\n')
            clean = '\n'.join(lines[1:-1])
        clean = clean.replace('```', '').strip()

        question = json.loads(clean)
        return Response({'question': question})

    except json.JSONDecodeError as e:
        print(f"Quiz JSON error: {e}")
        return Response(
            {'error': 'Could not parse quiz question. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        print(f"Quiz error: {e}")
        import traceback; traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def check_answer_view(request):
    try:
        question       = request.data.get('question', '')
        user_answer    = request.data.get('user_answer', '')
        correct_answer = request.data.get('correct_answer', '')
        level          = request.data.get('level', 'B1')

        feedback = call_with_retry(
            lambda: gemini_service.check_quiz_answer(
                question, user_answer, correct_answer, level
            )
        )
        return Response({'feedback': feedback})

    except Exception as e:
        print(f"Check answer error: {e}")
        import traceback; traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def progress_view(request):
    try:
        session_id = request.data.get('session_id', 'default')
        progress   = get_or_create_progress(session_id)

        if 'streak' in request.data:
            progress.streak = request.data['streak']
        if 'words_learned' in request.data:
            progress.words_learned = request.data['words_learned']
        if 'accuracy' in request.data:
            progress.accuracy = request.data['accuracy']
        if 'level' in request.data:
            progress.level = request.data['level']

        progress.save()

        # Check for auto level up
        level_up  = False
        old_level = progress.level

        thresholds = {
            'A1': {'words': 20,  'accuracy': 60},
            'A2': {'words': 50,  'accuracy': 65},
            'B1': {'words': 100, 'accuracy': 70},
            'B2': {'words': 200, 'accuracy': 75},
        }
        next_level = {
            'A1': 'A2',
            'A2': 'B1',
            'B1': 'B2',
            'B2': 'C1',
        }

        current = progress.level
        if current in thresholds:
            t = thresholds[current]
            if (progress.words_learned >= t['words'] and
                    progress.accuracy >= t['accuracy']):
                progress.level = next_level[current]
                level_up = True
                progress.save()
                print(f"🎉 User leveled up: {old_level} → {progress.level}")

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
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_progress_view(request):
    try:
        session_id = request.query_params.get('session_id', 'default')
        progress   = get_or_create_progress(session_id)

        return Response({
            'level':         progress.level,
            'streak':        progress.streak,
            'words_learned': progress.words_learned,
            'accuracy':      progress.accuracy,
        })

    except Exception as e:
        print(f"Get progress error: {e}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )