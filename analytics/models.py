from django.db import models
class NewsItem(models.Model):
    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Позитивный"
        NEUTRAL = "neutral", "Нейтральный"
        NEGATIVE = "negative", "Негативный"
    title = models.CharField(max_length=300)
    source = models.CharField(max_length=120)
    category = models.CharField(max_length=80, db_index=True)
    published_at = models.DateTimeField(db_index=True)
    summary = models.TextField()
    sentiment = models.CharField(max_length=12, choices=Sentiment.choices, default=Sentiment.NEUTRAL, db_index=True)
    relevance = models.PositiveSmallIntegerField(default=50)
    url = models.URLField(blank=True)
    is_demo = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ["-published_at"]
    def __str__(self): return self.title
class BusinessSignal(models.Model):
    class Severity(models.TextChoices):
        HIGH = "high", "Высокий"
        MEDIUM = "medium", "Средний"
        LOW = "low", "Низкий"
    title = models.CharField(max_length=240)
    horizon = models.CharField(max_length=80)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    confidence = models.PositiveSmallIntegerField(default=70)
    impact_area = models.CharField(max_length=120)
    rationale = models.TextField()
    next_step = models.CharField(max_length=300)
    source_count = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(default=True)
    class Meta:
        ordering = ["-confidence", "-created_at"]
    def __str__(self): return self.title
