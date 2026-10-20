import hashlib
from django.db import models
from django.utils import timezone

class Company(models.Model):
    company_id=models.CharField(max_length=100,unique=True,db_index=True)
    name=models.CharField(max_length=240)
    industry=models.CharField(max_length=240,blank=True)
    okved_code=models.CharField(max_length=24,blank=True)
    revenue_rub=models.DecimalField(max_digits=20,decimal_places=2,null=True,blank=True)
    employee_band=models.CharField(max_length=80,blank=True)
    region=models.CharField(max_length=160,blank=True)
    city=models.CharField(max_length=160,blank=True)
    company_age_band=models.CharField(max_length=80,blank=True)
    development_stage=models.CharField(max_length=120,blank=True)
    group_id=models.CharField(max_length=100,blank=True,db_index=True)
    products=models.JSONField(default=list,blank=True)
    export_countries=models.JSONField(default=list,blank=True)
    known_facts=models.JSONField(default=dict,blank=True)
    profile_provenance=models.JSONField(default=dict,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    is_demo=models.BooleanField(default=True,db_index=True)
    class Meta: ordering=["name"]
    def __str__(self): return self.name

class NewsItem(models.Model):
    class Sentiment(models.TextChoices):
        POSITIVE="positive","Позитивный"
        NEUTRAL="neutral","Нейтральный"
        NEGATIVE="negative","Негативный"
    title=models.CharField(max_length=300)
    source=models.CharField(max_length=120)
    category=models.CharField(max_length=80,db_index=True)
    published_at=models.DateTimeField(db_index=True)
    summary=models.TextField()
    sentiment=models.CharField(max_length=12,choices=Sentiment.choices,default=Sentiment.NEUTRAL,db_index=True)
    relevance=models.PositiveSmallIntegerField(default=50)
    url=models.URLField(blank=True)
    is_demo=models.BooleanField(default=True,db_index=True)
    content_hash=models.CharField(max_length=64,blank=True,db_index=True)
    event_date=models.DateTimeField(null=True,blank=True)
    entities=models.JSONField(default=list,blank=True)
    facts=models.JSONField(default=list,blank=True)
    class Meta: ordering=["-published_at"]
    def save(self,*args,**kwargs):
        if not self.content_hash:
            self.content_hash=hashlib.sha256(" ".join((self.title or "").lower().split()).encode()).hexdigest()
        super().save(*args,**kwargs)
    def __str__(self): return self.title

class BusinessSignal(models.Model):
    class Severity(models.TextChoices):
        HIGH="high","Высокий"
        MEDIUM="medium","Средний"
        LOW="low","Низкий"
    title=models.CharField(max_length=240)
    horizon=models.CharField(max_length=80)
    severity=models.CharField(max_length=10,choices=Severity.choices,default=Severity.MEDIUM)
    confidence=models.PositiveSmallIntegerField(default=70)
    impact_area=models.CharField(max_length=120)
    rationale=models.TextField()
    next_step=models.CharField(max_length=300)
    source_count=models.PositiveSmallIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
    is_demo=models.BooleanField(default=True)
    class Meta: ordering=["-confidence","-created_at"]
    def __str__(self): return self.title

class SourceDocument(models.Model):
    class Kind(models.TextChoices):
        EXTERNAL="external","Внешний источник"
        BANK="bank_analysis","Аналитика Альфа-Банка"
        DATASET="dataset","Набор данных"
    title=models.CharField(max_length=400)
    source_name=models.CharField(max_length=200)
    kind=models.CharField(max_length=24,choices=Kind.choices,db_index=True)
    url=models.URLField(blank=True)
    published_at=models.DateTimeField(null=True,blank=True)
    retrieved_at=models.DateTimeField(default=timezone.now)
    content=models.TextField()
    locator=models.CharField(max_length=240,blank=True)
    content_hash=models.CharField(max_length=64,unique=True)
    metadata=models.JSONField(default=dict,blank=True)
    is_demo=models.BooleanField(default=False)
    class Meta: ordering=["-published_at","-retrieved_at"]
    def save(self,*args,**kwargs):
        if not self.content_hash: self.content_hash=hashlib.sha256((self.title+self.content).encode()).hexdigest()
        super().save(*args,**kwargs)

class Insight(models.Model):
    class Priority(models.TextChoices):
        CRITICAL="critical","Критический"
        HIGH="high","Высокий"
        MEDIUM="medium","Средний"
        WATCH="watch","Наблюдение"
    company=models.ForeignKey(Company,on_delete=models.CASCADE,related_name="insights")
    title=models.CharField(max_length=300)
    summary=models.TextField()
    priority=models.CharField(max_length=12,choices=Priority.choices,default=Priority.MEDIUM)
    confidence=models.CharField(max_length=12,default="low")
    score=models.PositiveSmallIntegerField(default=0)
    event_ids=models.JSONField(default=list,blank=True)
    facts=models.JSONField(default=list,blank=True)
    company_exposure=models.JSONField(default=list,blank=True)
    bank_analysis=models.JSONField(default=list,blank=True)
    impact_mechanisms=models.JSONField(default=list,blank=True)
    risks=models.JSONField(default=list,blank=True)
    opportunities=models.JSONField(default=list,blank=True)
    scenarios=models.JSONField(default=list,blank=True)
    unknowns=models.JSONField(default=list,blank=True)
    recommended_checks=models.JSONField(default=list,blank=True)
    sources=models.JSONField(default=list,blank=True)
    trace=models.JSONField(default=list,blank=True)
    status=models.CharField(max_length=24,default="active",db_index=True)
    version=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=["-score","-updated_at"]

class AgentRun(models.Model):
    company=models.ForeignKey(Company,on_delete=models.CASCADE,related_name="agent_runs")
    insight=models.ForeignKey(Insight,null=True,blank=True,on_delete=models.SET_NULL)
    status=models.CharField(max_length=20,default="completed")
    plan=models.JSONField(default=list,blank=True)
    trace=models.JSONField(default=list,blank=True)
    model_name=models.CharField(max_length=100,blank=True)
    duration_ms=models.PositiveIntegerField(default=0)
    error_summary=models.CharField(max_length=500,blank=True)
    created_at=models.DateTimeField(default=timezone.now)

class Feedback(models.Model):
    company=models.ForeignKey(Company,on_delete=models.CASCADE)
    insight=models.ForeignKey(Insight,on_delete=models.CASCADE,related_name="feedback")
    kind=models.CharField(max_length=24,choices=[("useful","Полезно"),("irrelevant","Неактуально"),("incorrect","Ошибка"),("duplicate","Дубликат")])
    comment=models.CharField(max_length=1000,blank=True)
    created_at=models.DateTimeField(default=timezone.now)

class ChatMessage(models.Model):
    company=models.ForeignKey(Company,on_delete=models.CASCADE)
    insight=models.ForeignKey(Insight,on_delete=models.CASCADE,related_name="messages")
    role=models.CharField(max_length=12,choices=[("user","Пользователь"),("assistant","Ассистент")])
    content=models.TextField()
    citations=models.JSONField(default=list,blank=True)
    created_at=models.DateTimeField(default=timezone.now)

class PaymentRelationship(models.Model):
    payer=models.ForeignKey(Company,on_delete=models.CASCADE,related_name="outgoing_payments")
    beneficiary=models.ForeignKey(Company,on_delete=models.CASCADE,related_name="incoming_payments")
    payment_amount=models.DecimalField(max_digits=22,decimal_places=2,null=True,blank=True)
    payment_count=models.PositiveBigIntegerField(null=True,blank=True)
    source_file=models.CharField(max_length=240,blank=True)
    imported_at=models.DateTimeField(default=timezone.now)
    is_demo=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["payer","beneficiary","source_file"],name="uniq_payment_pair_source")]
        indexes=[models.Index(fields=["payer","beneficiary"])]
