"""Runtime configuration. Everything is read from the environment once at import."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name, default=False):
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


ALLOWED_LLM_MODELS = (
    "Gemma 4 26B A4B",
    "GLM-5.3-Flash",
    "Qwen3.6 35B A3B",
    "DeepSeek-V4.1-Flash",
    "Qwen3-VL-30B-A3B-Instruct",
    "Kimi-K2.6",
)


class Settings:
    env = os.getenv("RADAR_ENV", "development")
    debug = _bool("RADAR_DEBUG", False)
    secret_key = os.getenv("RADAR_SECRET_KEY", "")
    db_path = os.getenv("RADAR_DB_PATH", str(ROOT / "var" / "radar.sqlite3"))
    data_dir = Path(os.getenv("RADAR_DATA_DIR", str(ROOT / "data")))
    demo_password = os.getenv("RADAR_DEMO_PASSWORD", "alfa-radar-demo")
    seed_on_start = _bool("RADAR_SEED_ON_START", True)
    dataset = os.getenv("RADAR_DATASET", "auto")   # auto | contest | synthetic
    cookie_secure = _bool("RADAR_COOKIE_SECURE", False)
    session_minutes = _int("RADAR_SESSION_MINUTES", 480)

    # LLM gateway (OpenAI-compatible). Only names from ALLOWED_LLM_MODELS are accepted.
    llm_base_url = os.getenv("LLM_API_BASE_URL", "").strip().rstrip("/")
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    llm_model_light = os.getenv("LLM_MODEL_LIGHT", "Gemma 4 26B A4B").strip()
    llm_model_deep = os.getenv("LLM_MODEL_DEEP", "GLM-5.3-Flash").strip()
    llm_timeout = _int("LLM_TIMEOUT_SECONDS", 40)
    llm_daily_token_budget = _int("LLM_DAILY_TOKEN_BUDGET", 400_000)
    llm_run_token_budget = _int("LLM_RUN_TOKEN_BUDGET", 24_000)

    # Agent limits
    agent_max_steps = _int("AGENT_MAX_STEPS", 18)
    agent_max_replans = _int("AGENT_MAX_REPLANS", 2)
    agent_wall_seconds = _int("AGENT_WALL_SECONDS", 60)

    # Ingestion
    rss_feeds = [x.strip() for x in os.getenv("RSS_FEEDS", "").split(",") if x.strip()]
    http_timeout = _int("HTTP_TIMEOUT_SECONDS", 12)
    max_upload_mb = _int("MAX_UPLOAD_MB", 60)

    # Ranking
    rate_elevated_pct = float(os.getenv("RATE_ELEVATED_PCT", "10"))


settings = Settings()
