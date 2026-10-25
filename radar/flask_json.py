"""Make Flask's JSON provider keep Cyrillic readable and tolerate non-finite floats."""
import json
import math

from flask.json.provider import DefaultJSONProvider


class Provider(DefaultJSONProvider):
    ensure_ascii = False
    sort_keys = False

    def dumps(self, obj, **kw):
        kw.setdefault("ensure_ascii", False)
        return json.dumps(self._clean(obj), **kw)

    def _clean(self, o):
        if isinstance(o, float) and not math.isfinite(o):
            return None
        if isinstance(o, dict):
            return {k: self._clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple, set)):
            return [self._clean(v) for v in o]
        return o


def install(app):
    app.json = Provider(app)
