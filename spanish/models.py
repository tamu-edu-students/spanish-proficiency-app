from django.db import models

# ── User Progress ─────────────────────────────────────────────────────
# Stores each user's learning progress
# For now we use a simple session_id to identify users
# (no login required yet)
class UserProgress(models.Model):
    # A unique ID for this user's session
    session_id    = models.CharField(max_length=100, unique=True)

    # Their current CEFR level — A1 to B2
    level         = models.CharField(max_length=5, default='B1')

    # How many days in a row they've practiced
    streak        = models.IntegerField(default=0)

    # Total Spanish words they've learned
    words_learned = models.IntegerField(default=0)

    # Quiz accuracy as a percentage 0-100
    accuracy      = models.FloatField(default=0.0)

    # When they last practiced — used to calculate streak
    last_practice = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"User {self.session_id} — Level {self.level}"


# ── Flashcard ─────────────────────────────────────────────────────────
# Stores each vocabulary card and when it should be shown next
# This is the SRS (Spaced Repetition System) data
class FlashCard(models.Model):
    # Which user this card belongs to
    session_id  = models.CharField(max_length=100)

    # The Spanish word
    word        = models.CharField(max_length=200)

    # English translation
    translation = models.CharField(max_length=200)

    # An example sentence using the word
    example     = models.TextField(blank=True)

    # SRS fields — control when to show the card again
    # ease_factor starts at 2.5 — higher = shown less often
    ease_factor = models.FloatField(default=2.5)

    # How many days until we show this card again
    interval    = models.IntegerField(default=1)

    # How many times in a row the user got it right
    repetitions = models.IntegerField(default=0)

    # The date when this card should next appear
    next_review = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.word} → {self.translation}"


# ── Conversation History ───────────────────────────────────────────────
# Saves chat messages so users can see their past conversations
class ConversationMessage(models.Model):
    session_id = models.CharField(max_length=100)

    # "user" or "model" — who sent this message
    role       = models.CharField(max_length=10)

    # The actual message text
    content    = models.TextField()

    # When it was sent
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Always return messages in the order they were sent
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"