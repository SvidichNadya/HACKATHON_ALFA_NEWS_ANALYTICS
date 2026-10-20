import hashlib,io,json,re,urllib.request,xml.etree.ElementTree as ET
from django.conf import settings
from django.db.models import Count,Q
from django.http import JsonResponse,HttpResponseBadRequest
from django.shortcuts import render,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_protect
from .models import BusinessSignal,NewsItem,Company,SourceDocument,Insight,AgentRun,Feedback,ChatMessage
from .services import analyze_company,answer_question,classify,sentiment
def _company(request):
 companies=list(Company.objects.all()); selected=request.GET.get("company") or request.session.get("company_id")
 c=next((x for x in companies if str(x.pk)==str(selected)),companies[0] if companies else None)
 if c: request.session["company_id"]=c.pk
 return c
def dashboard(request):
 if not Company.objects.exists():
  from django.core.management import call_command
  call_command("seed_demo")
 c=_company(request); qs=NewsItem.objects.all(); q=request.GET.get("q","").strip(); cat=request.GET.get("category","all"); sen=request.GET.get("sentiment","all")
 if q: qs=qs.filter(Q(title__icontains=q)|Q(summary__icontains=q)|Q(source__icontains=q))
 if cat!="all": qs=qs.filter(category=cat)
 if sen!="all": qs=qs.filter(sentiment=sen)
 alln=NewsItem.objects.all()
 return render(request,"analytics/dashboard.html",{"company":c,"companies":Company.objects.all(),"news":qs[:12],"query":q,"selected_category":cat,"selected_sentiment":sen,"categories":NewsItem.objects.values_list("category",flat=True).distinct().order_by("category"),"total_news":alln.count(),"negative_news":alln.filter(sentiment="negative").count(),"signals":BusinessSignal.objects.all()[:4],"high_signals":BusinessSignal.objects.filter(severity="high").count(),"today_label":timezone.localdate().strftime("%d.%m.%Y"),"insights":c.insights.filter(status="active")[:8] if c else [],"bank_docs":SourceDocument.objects.filter(kind="bank_analysis").count(),"agent_runs":AgentRun.objects.count(),"feedback_count":Feedback.objects.count(),"latest_run":c.agent_runs.first() if c else None})
@require_GET
def overview_api(request):
 return JsonResponse({"sentiment":list(NewsItem.objects.values("sentiment").annotate(count=Count("id"))),"categories":list(NewsItem.objects.values("category").annotate(count=Count("id")).order_by("-count")[:8]),"news_total":NewsItem.objects.count(),"signals_total":BusinessSignal.objects.count()})
@require_GET
def signals_api(request):
 return JsonResponse({"signals":[{"id":s.id,"title":s.title,"severity":s.severity,"confidence":s.confidence,"impact_area":s.impact_area,"rationale":s.rationale,"next_step":s.next_step,"source_count":s.source_count} for s in BusinessSignal.objects.all()]})
@require_GET
def companies_api(request):
 return JsonResponse({"companies":[{"id":c.pk,"company_id":c.company_id,"name":c.name,"industry":c.industry,"revenue_rub":str(c.revenue_rub) if c.revenue_rub else None,"region":c.region,"products":c.products,"group_id":c.group_id,"known_facts":c.known_facts,"profile_provenance":c.profile_provenance} for c in Company.objects.all()]})
def _json(i):
 return {"id":i.pk,"company_id":i.company_id,"title":i.title,"summary":i.summary,"priority":i.priority,"confidence":i.confidence,"score":i.score,"facts":i.facts,"company_exposure":i.company_exposure,"bank_analysis":i.bank_analysis,"impact_mechanisms":i.impact_mechanisms,"risks":i.risks,"opportunities":i.opportunities,"scenarios":i.scenarios,"unknowns":i.unknowns,"recommended_checks":i.recommended_checks,"sources":i.sources,"trace":i.trace,"version":i.version,"created_at":i.created_at.isoformat()}
@require_POST
@csrf_protect
def analyze_api(request,company_id):
 c=get_object_or_404(Company,pk=company_id); i=analyze_company(c,request.POST.get("question","").strip()[:2000] or None); request.session["company_id"]=c.pk
 return JsonResponse({"insight":_json(i),"run_id":c.agent_runs.first().pk})
@require_GET
def insight_api(request,insight_id):
 i=get_object_or_404(Insight.objects.select_related("company"),pk=insight_id)
 return JsonResponse({"insight":_json(i),"company":{"id":i.company.pk,"name":i.company.name,"industry":i.company.industry}})
@require_POST
@csrf_protect
def chat_api(request,insight_id):
 i=get_object_or_404(Insight.objects.select_related("company"),pk=insight_id)
 try: b=json.loads(request.body or "{}")
 except json.JSONDecodeError:return HttpResponseBadRequest("Invalid JSON")
 q=str(b.get("question","")).strip()
 if not q or len(q)>2000:return HttpResponseBadRequest("Question must contain 1–2000 characters")
 ChatMessage.objects.create(company=i.company,insight=i,role="user",content=q); a,cites=answer_question(i.company,i,q); ChatMessage.objects.create(company=i.company,insight=i,role="assistant",content=a,citations=cites)
 return JsonResponse({"answer":a,"citations":cites})
@require_POST
@csrf_protect
def feedback_api(request,insight_id):
 i=get_object_or_404(Insight.objects.select_related("company"),pk=insight_id)
 try:b=json.loads(request.body or "{}")
 except json.JSONDecodeError:return HttpResponseBadRequest("Invalid JSON")
 kind=b.get("kind")
 if kind not in dict(Feedback._meta.get_field("kind").choices):return HttpResponseBadRequest("Unsupported feedback kind")
 f=Feedback.objects.create(company=i.company,insight=i,kind=kind,comment=str(b.get("comment",""))[:1000])
 return JsonResponse({"ok":True,"feedback_id":f.pk})
@require_POST
@csrf_protect
def import_news_api(request):
 feeds=[x.strip() for x in getattr(settings,"RSS_FEEDS",[]) if x.strip()]
 if not feeds:return JsonResponse({"ok":False,"error":"RSS_FEEDS не настроен в окружении."},status=400)
 created=skipped=0; errors=[]
 for feed in feeds[:20]:
  try:
   if not feed.startswith("https://"):raise ValueError("RSS feed must use HTTPS")
   req=urllib.request.Request(feed,headers={"User-Agent":"AlfaNewsIntelligence/1.0"})
   with urllib.request.urlopen(req,timeout=10) as r:data=r.read(5000000)
   root=ET.fromstring(data); entries=root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
   for e in entries[:100]:
    def child(*names):
     for name in names:
      n=e.find(name)
      if n is not None and n.text:return n.text.strip()
     return ""
    title=child("title","{http://www.w3.org/2005/Atom}title"); desc=child("description","summary","{http://www.w3.org/2005/Atom}summary","{http://www.w3.org/2005/Atom}content")
    link=child("link"); ln=e.find("{http://www.w3.org/2005/Atom}link")
    if not link and ln is not None:link=ln.attrib.get("href","")
    if not title:continue
    summary=re.sub("<[^>]+>"," ",desc)[:12000]; h=hashlib.sha256(" ".join(title.lower().split()).encode()).hexdigest()
    if NewsItem.objects.filter(content_hash=h).exists():skipped+=1;continue
    pub=timezone.now(); NewsItem.objects.create(title=title[:300],source=feed.split("/")[2][:120],category=classify(title+" "+summary),published_at=pub,summary=summary or title,sentiment=sentiment(title+" "+summary),url=link[:500],is_demo=False,content_hash=h)
    dh=hashlib.sha256((title+summary).encode()).hexdigest(); SourceDocument.objects.get_or_create(content_hash=dh,defaults={"title":title[:400],"source_name":feed.split("/")[2][:200],"kind":"external","url":link[:500],"published_at":pub,"content":summary or title,"is_demo":False});created+=1
  except Exception as e:errors.append({"feed":feed,"error":type(e).__name__})
 return JsonResponse({"ok":True,"created":created,"skipped_duplicates":skipped,"errors":errors})
@require_POST
@csrf_protect
def import_bank_api(request):
 f=request.FILES.get("file")
 if not f:return HttpResponseBadRequest("Прикрепите файл")
 if f.size>15*1024*1024:return HttpResponseBadRequest("Максимальный размер файла — 15 МБ")
 name=f.name.lower()
 try:
  raw=f.read()
  if name.endswith((".txt",".md",".csv")):content=raw.decode("utf-8-sig");loc="Текстовый файл"
  elif name.endswith(".pdf"):
   from pypdf import PdfReader
   reader=PdfReader(io.BytesIO(raw));content="\n".join(p.extract_text() or "" for p in reader.pages);loc=f"PDF, страниц: {len(reader.pages)}"
  elif name.endswith(".docx"):
   from docx import Document
   doc=Document(io.BytesIO(raw));content="\n".join(p.text for p in doc.paragraphs);loc="DOCX, извлечённый текст"
  else:return HttpResponseBadRequest("Поддерживаются TXT, MD, CSV, PDF, DOCX")
 except Exception as e:return HttpResponseBadRequest("Не удалось извлечь текст: "+type(e).__name__)
 if not content.strip():return HttpResponseBadRequest("В документе не найден текст")
 title=f.name[:400];h=hashlib.sha256((title+content).encode()).hexdigest()
 d,created=SourceDocument.objects.get_or_create(content_hash=h,defaults={"title":title,"source_name":"Загруженная аналитика Альфа-Банка","kind":"bank_analysis","content":content[:1000000],"locator":loc,"is_demo":False})
 return JsonResponse({"ok":True,"document_id":d.pk,"created":created,"characters":len(content),"message":"Материал сохранён отдельно как BANK_ANALYSIS."})
@require_GET
def agent_runs_api(request):
 c=_company(request); qs=AgentRun.objects.filter(company=c) if c else AgentRun.objects.none()
 return JsonResponse({"runs":[{"id":r.pk,"insight_id":r.insight_id,"status":r.status,"plan":r.plan,"trace":r.trace,"model":r.model_name,"duration_ms":r.duration_ms,"created_at":r.created_at.isoformat()} for r in qs[:50]})
