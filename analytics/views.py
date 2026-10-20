from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from .models import BusinessSignal, NewsItem

def dashboard(request):
    qs = NewsItem.objects.all()
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "all")
    sentiment = request.GET.get("sentiment", "all")
    if query: qs = qs.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(source__icontains=query))
    if category != "all": qs = qs.filter(category=category)
    if sentiment != "all": qs = qs.filter(sentiment=sentiment)
    all_news = NewsItem.objects.all()
    context = {"news": qs[:12], "query": query, "selected_category": category, "selected_sentiment": sentiment,
        "categories": NewsItem.objects.values_list("category", flat=True).distinct().order_by("category"),
        "total_news": all_news.count(), "negative_news": all_news.filter(sentiment="negative").count(),
        "signals": BusinessSignal.objects.all()[:4], "high_signals": BusinessSignal.objects.filter(severity="high").count(),
        "today_label": timezone.localdate().strftime("%d.%m.%Y")}
    return render(request, "analytics/dashboard.html", context)

def overview_api(request):
    sentiment = list(NewsItem.objects.values("sentiment").annotate(count=Count("id")).order_by("sentiment"))
    categories = list(NewsItem.objects.values("category").annotate(count=Count("id")).order_by("-count")[:8])
    return JsonResponse({"sentiment": sentiment, "categories": categories, "news_total": NewsItem.objects.count(), "signals_total": BusinessSignal.objects.count()})

def signals_api(request):
    return JsonResponse({"signals": [{"id": s.id, "title": s.title, "severity": s.severity, "confidence": s.confidence, "impact_area": s.impact_area, "rationale": s.rationale, "next_step": s.next_step, "source_count": s.source_count} for s in BusinessSignal.objects.all()]})
