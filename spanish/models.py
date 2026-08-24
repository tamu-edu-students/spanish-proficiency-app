from django.db import models


# User Progress
class UserProgress(models.Model):

    session_id    = models.CharField(max_length=100, unique=True)
    netid         = models.CharField(max_length=50, blank=True, default='')
    level         = models.CharField(max_length=5, default='B1')
    streak        = models.IntegerField(default=0)
    words_learned = models.IntegerField(default=0)
    accuracy      = models.FloatField(default=0.0)
    last_practice = models.DateTimeField(auto_now=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    # Tracks last visit date for streak calculation across all browsers/devices
    last_visit    = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-last_practice']

    def __str__(self):
        identifier = self.netid if self.netid else self.session_id
        return f"{identifier} - Level {self.level}"


# Flashcard
class FlashCard(models.Model):

    session_id  = models.CharField(max_length=100)
    word        = models.CharField(max_length=200)
    translation = models.CharField(max_length=200)
    example     = models.TextField(blank=True)
    ease_factor = models.FloatField(default=2.5)
    interval    = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=0)
    next_review = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.word} - {self.translation}"


# Conversation History
class ConversationMessage(models.Model):

    session_id = models.CharField(max_length=100)
    role       = models.CharField(max_length=10)
    content    = models.TextField()
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"