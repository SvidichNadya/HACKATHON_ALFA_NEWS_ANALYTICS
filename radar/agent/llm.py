"""Gateway client for the allowed models only. OpenAI-compatible chat completions, JSON output, token accounting."""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from ..config import ALLOWED_LLM_MODELS, settings


class LLMError(Exception):
    pass


class BudgetExceeded(LLMError):
    pass


def _day():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_json(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except ValueError:
        pass
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            depth += (t[i] == "{") - (t[i] == "}")
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except ValueError:
                    break
        start = t.find("{", start + 1)
    raise LLMError("Модель вернула ответ не в формате JSON")


class LLM:
    def __init__(self, db, base_url=None, api_key=None, light=None, deep=None, transport=None):
        self.db = db
        self.base = (base_url if base_url is not None else settings.llm_base_url)
        self.key = api_key if api_key is not None else settings.llm_api_key
        self.light = light or settings.llm_model_light
        self.deep = deep or settings.llm_model_deep
        self.transport = transport
        for m in (self.light, self.deep):
            if m not in ALLOWED_LLM_MODELS:
                raise LLMError(f"Модель «{m}» не входит в список разрешённых")

    @property
    def configured(self):
        return bool(self.base and (self.key or self.transport))

    def tokens_today(self):
        r = self.db.one("SELECT tokens FROM token_ledger WHERE day=?", (_day(),))
        return r["tokens"] if r else 0

    def _spend(self, n):
        self.db.x("INSERT INTO token_ledger(day,tokens) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET tokens=tokens+excluded.tokens", (_day(), n))

    def _post(self, payload):
        if self.transport:
            return self.transport(payload)
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        try:
            with urllib.request.urlopen(req, timeout=settings.llm_timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise LLMError(f"Шлюз LLM вернул HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise LLMError("Шлюз LLM недоступен") from e

    def chat_json(self, tier, system, user, max_tokens=1400, run_budget=None, temperature=0.2):
        """Returns (data, usage, model). run_budget is a mutable dict {'left': int}."""
        if not self.configured:
            raise LLMError("LLM не настроена")
        model = self.deep if tier == "deep" else self.light
        if self.tokens_today() >= settings.llm_daily_token_budget:
            raise BudgetExceeded("Суточный лимит токенов исчерпан")
        if run_budget is not None and run_budget["left"] <= 0:
            raise BudgetExceeded("Лимит токенов на анализ исчерпан")
        last = None
        for attempt in range(2):
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            if attempt:
                msgs.append({"role": "user", "content": "Предыдущий ответ не удалось разобрать. Верни только корректный JSON без пояснений."})
            t0 = time.time()
            resp = self._post({"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature,
                               "response_format": {"type": "json_object"}})
            u = resp.get("usage") or {}
            used = int(u.get("total_tokens") or (len(system) + len(user)) // 3 + max_tokens // 3)
            self._spend(used)
            if run_budget is not None:
                run_budget["left"] -= used
            usage = {"in": int(u.get("prompt_tokens") or 0), "out": int(u.get("completion_tokens") or 0), "total": used, "ms": int((time.time() - t0) * 1000)}
            try:
                content = resp["choices"][0]["message"]["content"]
                return parse_json(content), usage, model
            except (KeyError, IndexError, TypeError, LLMError) as e:
                last = e
        raise LLMError(str(last))
