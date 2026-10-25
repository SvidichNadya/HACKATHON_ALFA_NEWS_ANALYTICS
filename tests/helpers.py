import json
import os
import tempfile

os.environ.setdefault("RADAR_SECRET_KEY", "test-secret")
os.environ["RADAR_DATASET"] = "synthetic"
from radar.db import DB
from radar.seed import loader

_cache = {}


def seeded_db():
    if "db" not in _cache:
        d = tempfile.mkdtemp()
        db = DB(os.path.join(d, "t.sqlite3"))
        loader.bootstrap(db)
        _cache["db"] = db
    return _cache["db"]


def fresh_db():
    d = tempfile.mkdtemp()
    db = DB(os.path.join(d, "f.sqlite3"))
    db.migrate()
    return db


def fake_llm(narrative=None, fail=False, bad_json=False, usage=900):
    """OpenAI-compatible transport stub. Returns the given narrative items as the model's answer."""
    calls = []

    def transport(payload):
        calls.append(payload)
        if fail:
            from radar.agent.llm import LLMError
            raise LLMError("gateway down")
        content = "not json at all" if bad_json else json.dumps({"narrative": narrative or [], "open_questions": [], "answer": narrative or []}, ensure_ascii=False)
        return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": usage - 100, "completion_tokens": 100, "total_tokens": usage}}
    transport.calls = calls
    return transport
