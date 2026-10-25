"""HTTP layer: sessions, CSRF, tenant isolation, security headers, JSON API, static SPA."""
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash

from .. import evaluation
from ..agent.tools import Forbidden
from ..config import ROOT, settings
from ..db import DB
from ..flask_json import install as install_json
from ..knowledge.ontology import ROLE_LABELS
from ..seed import loader
from ..services import NotFound, Service

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class RateLimiter:
    def __init__(self, limit, window):
        self.limit, self.window, self.hits = limit, window, defaultdict(deque)

    def blocked(self, key):
        now, q = time.time(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return len(q) >= self.limit

    def hit(self, key):
        self.hits[key].append(time.time())

    def reset(self, key):
        self.hits.pop(key, None)

    def ok(self, key):
        now, q = time.time(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def _secret():
    if settings.secret_key:
        return settings.secret_key
    path = Path(settings.db_path).parent / "secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        os.chmod(path, 0o600)
    return path.read_text().strip()


def create_app(db_path=None, bootstrap=True, llm_transport=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=_secret(), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=settings.cookie_secure,
                      MAX_CONTENT_LENGTH=settings.max_upload_mb * 1024 * 1024, JSON_AS_ASCII=False)
    db = DB(db_path or settings.db_path)
    db.migrate()
    if bootstrap and settings.seed_on_start:
        loader.bootstrap(db)
    svc = Service(db)
    if llm_transport:
        svc.llm.transport = llm_transport
        svc.llm.base = svc.llm.base or "http://fake"
    app.extensions["svc"] = svc
    limiter = RateLimiter(30, 60)
    login_limiter = RateLimiter(8, 300)
    install_json(app)

    def err(msg, code=400, **extra):
        return jsonify({"error": msg, **extra}), code

    @app.errorhandler(Forbidden)
    def _forbidden(e):
        return err(str(e), 403)

    @app.errorhandler(NotFound)
    def _nf(e):
        return err(str(e), 404)

    @app.errorhandler(ValueError)
    def _val(e):
        return err(str(e), 400)

    @app.errorhandler(413)
    def _big(e):
        return err("Файл слишком большой", 413)

    @app.errorhandler(Exception)
    def _any(e):
        app.logger.exception("unhandled")
        if app.debug:
            raise e
        return err("Внутренняя ошибка сервиса. Запрос записан в журнал.", 500)

    @app.before_request
    def _auth():
        g.user = None
        if session.get("uid"):
            g.user = db.one("SELECT id,login,name,role,is_admin FROM users WHERE id=?", (session["uid"],))
        if request.path.startswith("/api/") and request.path not in ("/api/login", "/api/health", "/api/me"):
            if not g.user:
                return err("Требуется вход", 401)
        if request.method in ("POST", "PUT", "DELETE") and request.path.startswith("/api/") and request.path != "/api/login":
            tok = request.headers.get("X-CSRF-Token", "")
            if not session.get("csrf") or not secrets.compare_digest(tok, session["csrf"]):
                return err("Недействительный токен защиты запроса", 403)

    @app.after_request
    def _headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ------------------------------------------------------------ session
    @app.post("/api/login")
    def login():
        d = request.get_json(silent=True) or {}
        key = request.remote_addr or "?"
        if login_limiter.blocked(key):
            return err("Слишком много неудачных попыток входа. Повторите позже.", 429)
        u = db.one("SELECT * FROM users WHERE login=?", ((d.get("login") or "").strip().lower(),))
        if not u or not check_password_hash(u["pw_hash"], d.get("password") or ""):
            login_limiter.hit(key)
            db.x("INSERT INTO audit(ts,actor,action,target,allowed,detail) VALUES (?,?,?,?,?,?)", (loader.store.now_iso(), "user", "login", d.get("login", "")[:60], 0, "неверные данные"))
            return err("Неверный логин или пароль", 401)
        login_limiter.reset(key)
        session.clear()
        session["uid"], session["csrf"] = u["id"], secrets.token_urlsafe(24)
        session.permanent = True
        db.x("INSERT INTO audit(ts,user_id,actor,action,target,allowed) VALUES (?,?,?,?,?,1)", (loader.store.now_iso(), u["id"], "user", "login", u["login"]))
        return jsonify({"ok": True})

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me():
        if not g.user:
            # Build the demo list from accounts that actually exist in this database.
            # This keeps the login screen in sync with the selected dataset (contest or synthetic).
            accounts = db.q("SELECT login, name, role, is_admin FROM users ORDER BY is_admin, name, login")
            demo_accounts = [
                {
                    "login": a["login"],
                    "name": a["name"],
                    "role": "доступ ко всем компаниям" if a["is_admin"] else ROLE_LABELS.get(a["role"], a["role"]),
                }
                for a in accounts
            ]
            return jsonify({"user": None, "demo_accounts": demo_accounts,
                            "demo_password_hint": "см. README (RADAR_DEMO_PASSWORD)"}), 200
        u = g.user
        return jsonify({"user": {**u, "role_label": ROLE_LABELS.get(u["role"], u["role"])}, "csrf": session["csrf"], "roles": ROLE_LABELS,
                        "companies": svc.companies_for(u), "llm": svc.llm_status()})

    @app.get("/api/health")
    def health():
        db.one("SELECT 1")
        return jsonify({"status": "ok", "llm_configured": svc.llm.configured})

    # ------------------------------------------------------------ data
    @app.get("/api/companies")
    def companies():
        return jsonify({"companies": svc.companies_for(g.user, request.args.get("q"))})

    @app.get("/api/companies/<cid>/feed")
    def feed(cid):
        return jsonify(svc.feed(g.user, cid, request.args.get("role") or None))

    @app.post("/api/companies/<cid>/seen")
    def seen(cid):
        svc.mark_seen(g.user, cid)
        return jsonify({"ok": True})

    @app.get("/api/companies/<cid>/network")
    def network(cid):
        return jsonify(svc.network(g.user, cid))

    @app.get("/api/companies/<cid>/events/<int:eid>/insight")
    def event_insight(cid, eid):
        if not limiter.ok(f"an{g.user['id']}"):
            return err("Слишком много запросов на анализ. Подождите минуту.", 429)
        ins = svc.event_insight(g.user, cid, eid, request.args.get("role") or None, request.args.get("refresh") == "1")
        ins["calc_specs"] = svc.calc_specs(g.user, cid, ins.get("calc", []))
        return jsonify(ins)

    @app.post("/api/companies/<cid>/cascades/<key>/analyze")
    def cascade(cid, key):
        if not limiter.ok(f"an{g.user['id']}"):
            return err("Слишком много запросов на анализ. Подождите минуту.", 429)
        ins = svc.cascade_insight(g.user, cid, key, (request.get_json(silent=True) or {}).get("role"))
        ins["calc_specs"] = svc.calc_specs(g.user, cid, ins.get("calc", []))
        return jsonify(ins)

    @app.post("/api/companies/<cid>/analyze")
    def adhoc(cid):
        if not limiter.ok(f"an{g.user['id']}"):
            return err("Слишком много запросов на анализ. Подождите минуту.", 429)
        d = request.get_json(silent=True) or {}
        out = svc.adhoc(g.user, cid, (d.get("title") or "")[:300], (d.get("text") or "")[:60000], (d.get("url") or None), d.get("role"))
        if out.get("insight"):
            out["insight"]["calc_specs"] = svc.calc_specs(g.user, cid, out["insight"].get("calc", []))
        return jsonify(out)

    @app.get("/api/insights/<int:iid>")
    def insight(iid):
        from ..agent.orchestrator import load_insight
        ins = load_insight(db, iid)
        if not ins:
            raise NotFound("Инсайт не найден")
        svc.ctx(g.user, ins["company_id"])
        ins["calc_specs"] = svc.calc_specs(g.user, ins["company_id"], ins.get("calc", []))
        return jsonify(ins)

    @app.post("/api/insights/<int:iid>/chat")
    def chat(iid):
        if not limiter.ok(f"ch{g.user['id']}"):
            return err("Слишком много вопросов. Подождите минуту.", 429)
        q = ((request.get_json(silent=True) or {}).get("question") or "").strip()
        if len(q) < 3:
            return err("Сформулируйте вопрос подробнее")
        return jsonify(svc.ask(g.user, iid, q[:800]))

    @app.get("/api/insights/<int:iid>/chat")
    def history(iid):
        return jsonify({"messages": svc.history(g.user, iid)})

    @app.post("/api/insights/<int:iid>/feedback")
    def feedback(iid):
        d = request.get_json(silent=True) or {}
        return jsonify(svc.feedback(g.user, iid, d.get("kind"), d.get("comment", "")))

    @app.post("/api/companies/<cid>/calc")
    def calc(cid):
        d = request.get_json(silent=True) or {}
        return jsonify(svc.calc(g.user, cid, d.get("kind"), d.get("inputs") or {}))

    @app.get("/api/runs/<int:rid>")
    def run_trace(rid):
        return jsonify(svc.trace(g.user, rid))

    # ------------------------------------------------------------ library & quality
    @app.get("/api/library")
    def library():
        return jsonify(svc.library(g.user))

    @app.post("/api/library/upload")
    def upload():
        f = request.files.get("file")
        if not f or not f.filename:
            return err("Выберите файл")
        return jsonify(svc.upload_doc(g.user, os.path.basename(f.filename), f.read(), request.form.get("kind", "news")))

    @app.post("/api/library/feed")
    def pull():
        url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
        if not url:
            return err("Укажите адрес ленты")
        return jsonify(svc.pull_feed(g.user, url))

    @app.get("/api/metrics")
    def metrics():
        return jsonify(svc.metrics(g.user))

    @app.get("/api/evaluation")
    def evaluation_view():
        r = evaluation.run(db)
        return jsonify(r or {"companies": [], "mean": {}, "note": "Нет размеченных материалов для оценки."})

    # ------------------------------------------------------------ static
    static_dir = ROOT / "static"

    @app.get("/")
    def index():
        return send_from_directory(ROOT / "templates", "index.html")

    @app.get("/static/<path:p>")
    def static_files(p):
        r = send_from_directory(static_dir, p)
        r.headers["Cache-Control"] = "no-cache"
        return r

    return app


app = None


def wsgi():
    global app
    if app is None:
        app = create_app()
    return app
