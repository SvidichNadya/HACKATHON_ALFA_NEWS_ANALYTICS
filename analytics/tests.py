import json
from django.test import TestCase
from django.utils import timezone
from .models import Company,NewsItem,Feedback
from .services import classify,sentiment,relevance,analyze_company
class IntelligenceTests(TestCase):
 def setUp(self):
  self.company=Company.objects.create(company_id="TEST-1",name="ПромТест",industry="Металлургия",revenue_rub=10000000000,region="Уральский федеральный округ",products=["credit"],known_facts={"credit_product":True})
  self.news=NewsItem.objects.create(title="Высокая ключевая ставка сохраняет стоимость финансирования",source="Тест",category="Финансирование",published_at=timezone.now(),summary="Стоимость кредитов может оставаться повышенной.")
 def test_classification_sentiment(self):
  self.assertEqual(classify("Ключевая ставка и кредитование"),"Финансирование")
  self.assertEqual(sentiment("Рост затрат и риск дефицита"),"negative")
 def test_relevance(self):
  score,reasons=relevance(self.news,self.company);self.assertGreaterEqual(score,0);self.assertLessEqual(score,100);self.assertIsInstance(reasons,list)
 def test_pipeline_persists_trace(self):
  i=analyze_company(self.company);self.assertTrue(i.trace);self.assertTrue(i.unknowns);self.assertTrue(self.company.agent_runs.filter(insight=i).exists())
 def test_dashboard_api(self):
  self.assertEqual(self.client.get("/").status_code,200);self.assertEqual(self.client.get("/api/companies/").status_code,200)
 def test_feedback_persists(self):
  i=analyze_company(self.company);r=self.client.post(f"/api/insights/{i.pk}/feedback/",data=json.dumps({"kind":"useful"}),content_type="application/json");self.assertEqual(r.status_code,200);self.assertEqual(Feedback.objects.filter(insight=i).count(),1)
