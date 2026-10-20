from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import NewsItem, BusinessSignal, Company, SourceDocument
import hashlib

class Command(BaseCommand):
    help="Create idempotent synthetic companies, news, and clearly marked illustrative documents."
    def handle(self,*args,**options):
        now=timezone.now()
        companies=[
          {"company_id":"SYNTH-IND-001","name":"СеверПром Групп (синтетическая компания)","industry":"Промышленное производство","okved_code":"24.10","revenue_rub":18500000000,"employee_band":"5 000–10 000","region":"Свердловская область","city":"Екатеринбург","company_age_band":"15–25 лет","development_stage":"Зрелый бизнес","group_id":"SYNTH-GROUP-01","products":["credit","leasing","settlement_account"],"export_countries":["Казахстан","Беларусь"],"known_facts":{"credit_product":True,"leasing_product":True,"export_flag":True,"payment_concentration":"unknown"},"profile_provenance":{"industry":"Синтетический набор конкурса","revenue_rub":"Синтетическое значение","products":"Синтетический набор конкурса","export_countries":"Синтетический набор конкурса"}},
          {"company_id":"SYNTH-TRADE-002","name":"Вектор Дистрибуция (синтетическая компания)","industry":"Оптовая торговля","okved_code":"46.90","revenue_rub":26400000000,"employee_band":"1 000–5 000","region":"Москва","city":"Москва","company_age_band":"10–15 лет","development_stage":"Рост","group_id":"SYNTH-GROUP-02","products":["settlement_account","factoring","guarantees"],"export_countries":[],"known_facts":{"credit_product":False,"factoring_product":True,"payment_concentration":"unknown"},"profile_provenance":{"industry":"Синтетический набор конкурса","revenue_rub":"Синтетическое значение","products":"Синтетический набор конкурса"}},
          {"company_id":"SYNTH-FOOD-003","name":"Баланс АгроФуд (синтетическая компания)","industry":"Производство пищевых продуктов","okved_code":"10.89","revenue_rub":32100000000,"employee_band":"10 000–15 000","region":"Краснодарский край","city":"Краснодар","company_age_band":"25+ лет","development_stage":"Зрелый бизнес","group_id":"SYNTH-GROUP-03","products":["credit","settlement_account","deposits"],"export_countries":["Турция","Казахстан"],"known_facts":{"credit_product":True,"export_flag":True,"payment_concentration":"unknown"},"profile_provenance":{"industry":"Синтетический набор конкурса","revenue_rub":"Синтетическое значение","products":"Синтетический набор конкурса","export_countries":"Синтетический набор конкурса"}}
        ]
        for item in companies: Company.objects.update_or_create(company_id=item["company_id"],defaults={**item,"is_demo":True})
        items=[
          ("ЦБ сохраняет жёсткий сигнал по инфляции","Демо-источник: макрообзор","Макроэкономика","negative",94,"Риторика регулятора может указывать на то, что стоимость фондирования останется повышенной дольше базового сценария. Материал синтетический; это не фактическая публикация."),
          ("Ритейл ускоряет переход к собственным платёжным сценариям","Синтетическая отраслевая сводка","Конкуренция","neutral",88,"Условный пример развития собственных цифровых сервисов торговых сетей. Материал синтетический."),
          ("Компании пересматривают инвестиционные планы на следующий квартал","Синтетическая отраслевая сводка","Корпоративный сектор","negative",86,"Условный сигнал об отсрочке капитальных расходов в отдельных отраслях. Нельзя переносить на весь рынок без проверки."),
          ("Рынок цифровых платежей растёт быстрее наличного оборота","Синтетический технологический обзор","Технологии","positive",81,"Иллюстративный сценарий роста цифровых платежей, не является реальной публикацией."),
          ("Экспортёры обсуждают новые маршруты поставок","Синтетическая сводка внешней торговли","Внешняя торговля","neutral",78,"Условный пример изменения логистики, который может перераспределять валютные потоки и сроки поставок."),
          ("Участники рынка отмечают рост мошеннических сценариев с дипфейками","Синтетический обзор киберрисков","Технологии","negative",96,"Иллюстративный сигнал о социальной инженерии. Не подтверждает фактический рост инцидентов."),
          ("Регуляторы обсуждают раскрытие рисков алгоритмических решений","Синтетическая правовая сводка","Регулирование","neutral",84,"Условный сигнал для демонстрации контроля объяснимости и аудита автоматизированных решений."),
          ("Промышленность чувствительна к стоимости ресурсов","Синтетический отраслевой обзор","Инфляция и издержки","negative",75,"Иллюстративный материал о том, как рост цен на ресурсы может повлиять на себестоимость при наличии соответствующей экспозиции."),
          ("Потребительский спрос неоднороден по регионам","Синтетическая рыночная сводка","Отраслевые изменения","neutral",70,"Синтетический пример: нельзя обобщать наблюдение на всю отрасль без данных.")
        ]
        for i,(title,source,category,sentiment,relevance,summary) in enumerate(items):
            h=hashlib.sha256(" ".join(title.lower().split()).encode()).hexdigest()
            NewsItem.objects.update_or_create(content_hash=h,defaults={"title":title,"source":source,"category":category,"sentiment":sentiment,"relevance":relevance,"summary":summary,"published_at":now-timedelta(hours=i*3+1),"event_date":None,"url":"","is_demo":True})
        bank_examples=[
          ("Иллюстративный пример банковской аналитики: ключевая ставка","Условный материал для демонстрации схемы импорта","В учебном примере высокая ставка может означать, что стоимость заёмного финансирования снижается медленнее ожиданий. Это НЕ официальная позиция Альфа-Банка и НЕ реальный аналитический материал. Для использования в конкурсном выводе замените этот документ предоставленным организаторами оригиналом."),
          ("Иллюстративный пример банковской аналитики: инфляция и издержки","Условный материал для демонстрации схемы импорта","В учебном примере динамика инфляции рассматривается как фактор закупочных затрат. Это синтетический текст, не официальный материал и не экспертная позиция Альфа-Банка. Импортируйте реальный документ из комплекта кейса.")
        ]
        for title,source,content in bank_examples:
            h=hashlib.sha256((title+content).encode()).hexdigest()
            SourceDocument.objects.update_or_create(content_hash=h,defaults={"title":title,"source_name":source,"kind":"bank_analysis","content":content,"locator":"Синтетический учебный текст","is_demo":True})
        signals=[
          {"title":"Сочетание дорогого финансирования и ресурсных затрат требует проверки","horizon":"Сценарий · ближайшие кварталы","severity":"high","confidence":55,"impact_area":"Финансирование и себестоимость","rationale":"Демонстрационная гипотеза. Значимость зависит от реальных условий кредитов, закупочных договоров и доли соответствующих затрат; эти параметры в профиле не подтверждены.","next_step":"Проверить график финансирования, условия пересмотра ставок и долю чувствительных затрат","source_count":2},
          {"title":"Внешнеторговая экспозиция может менять требования к оборотному капиталу","horizon":"Сценарий · 1–2 квартала","severity":"medium","confidence":45,"impact_area":"Поставки и расчёты","rationale":"Гипотеза актуальна только для компании с подтверждёнными экспортными/импортными операциями; наличие страны в синтетическом профиле само по себе не доказывает объём торговли.","next_step":"Подтвердить долю внешнеторговых операций, валюту контрактов и сроки расчётов","source_count":2}]
        for item in signals: BusinessSignal.objects.get_or_create(title=item["title"],is_demo=True,defaults=item)
        self.stdout.write(self.style.SUCCESS("Synthetic dataset is ready; all demo bank documents are explicitly marked as synthetic."))
