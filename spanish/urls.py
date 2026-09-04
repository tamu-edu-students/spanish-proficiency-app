from django.urls import path
from . import views

urlpatterns = [
    path('chat/',         views.chat_view,          name='chat'),
    path('flashcards/',   views.flashcards_view,    name='flashcards'),
    path('quiz/',         views.quiz_view,           name='quiz'),
    path('quiz/batch/', views.quiz_batch_view),
    path('quiz/reading/', views.reading_quiz_view, name='reading_quiz'),
    path('quiz/check/',   views.check_answer_view,  name='check_answer'),
    path('progress/',     views.progress_view,       name='progress'),
    path('progress/get/', views.get_progress_view,  name='get_progress'),

    # ── Grading ───────────────────────────────────────────────
    path('grade/prompt/', views.grade_prompt_view,  name='grade_prompt'),
    path('grade/essay/',  views.grade_essay_view,   name='grade_essay'),
    path('grade/audio/',  views.grade_audio_view,   name='grade_audio'),
    path('grade/history/', views.submissions_view,  name='submissions'),

    # ── Authentication ────────────────────────────────────────
    # Returns current logged in user info
    # React calls this on app load to check if user is logged in
    path('me/',           views.get_current_user,   name='current_user'),
]