"""Minimal Venice.ai client (OpenAI-compatible). The key only ever goes in the Authorization header."""
import copy
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://api.venice.ai/api/v1"
VENICE_PARAMS = {"include_venice_system_prompt": False, "enable_web_search": "off"}
TIMEOUT = 60

MESSAGES = {
    401: "Your Venice key was rejected. Set it again in Settings > Vision Plus.",
    402: "Your Venice balance is empty.",
    429: "Venice is rate-limiting you. Wait a minute.",
}
NO_ANSWER = "Venice didn't answer. Try again."
_THINK = re.compile(r"<think>.*?</think>", re.S)


class VeniceError(RuntimeError):
    pass


class ModelMissing(VeniceError):
    """The model id isn't (or is no longer) in Venice's catalog."""


def _base(model: str, messages: list) -> dict:
    return {"model": model, "messages": messages, "temperature": 0.3, "reasoning_effort": "low",
            "venice_parameters": dict(VENICE_PARAMS)}


def build_chat_body(model: str, system: str, turns: list, max_tokens: int = 4000) -> dict:
    body = _base(model, [{"role": "system", "content": system}] + list(turns))
    body["max_completion_tokens"] = max_tokens
    return body


def strictify(schema: dict) -> dict:
    """Venice strict json_schema: every object closed and every property required."""
    s = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(s)
    return s


def build_tour_body(model: str, system: str, user: str, schema: dict) -> dict:
    body = _base(model, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    body["max_completion_tokens"] = 8000
    body["response_format"] = {"type": "json_schema", "json_schema": {"name": "tour", "strict": True, "schema": strictify(schema)}}
    return body


def reply_text(resp: dict):
    choice = (resp.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    return _THINK.sub("", content).strip(), choice.get("finish_reason") == "length"


def _cost(data: dict):
    usage = data.get("usage") or {}
    cost = usage.get("cost", data.get("cost"))
    if isinstance(cost, dict):
        cost = cost.get("usd")
    return float(cost) if isinstance(cost, (int, float)) else None


class Client:
    _models_cache = {"at": 0.0, "data": None}

    def __init__(self, key: str, opener=urllib.request.urlopen):
        self.key, self.opener = key, opener

    def _request(self, path: str, body=None, timeout: int = TIMEOUT) -> dict:
        req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                     method="GET" if body is None else "POST")
        req.add_header("Authorization", "Bearer " + self.key)
        req.add_header("Content-Type", "application/json")
        for attempt in (1, 2):
            try:
                with self.opener(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise ModelMissing("That Venice model isn't available any more.") from None
                if e.code in MESSAGES:
                    raise VeniceError(MESSAGES[e.code]) from None
                if e.code < 500 or attempt == 2:  # 4xx is never retried (Venice locks keys after many failed 4xx)
                    raise VeniceError(NO_ANSWER if e.code >= 500 else f"Venice refused the request ({e.code}).") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 2:
                    raise VeniceError(NO_ANSWER) from None

    def chat(self, body: dict, timeout: int = TIMEOUT) -> dict:
        data = self._request("/chat/completions", body, timeout)
        data["_cost_usd"] = _cost(data)
        return data

    def models(self) -> list:
        cache = Client._models_cache
        if cache["data"] is None or time.time() - cache["at"] > 900:
            cache["data"], cache["at"] = self._request("/models?type=text").get("data", []), time.time()
        return cache["data"]
