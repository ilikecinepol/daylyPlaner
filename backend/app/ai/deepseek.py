"""DeepSeek adapter; credentials never fall back to another provider's key."""
import json
import os
import httpx
from .schemas import ModelAnswer

DEFAULT_MODEL = "deepseek-v4-flash"

def model_name():
    return os.getenv("DEEPSEEK_MODEL", "").strip() or DEFAULT_MODEL

async def generate(message, context, instructions):
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DeepSeek is not configured")
    example = {"answer":"Предлагаю создать задачу. Подтвердите перед сохранением.",
               "proposals":[{"kind":"create_task","task_id":None,"changes":{"title":"Подготовить отчёт"}}]}
    prompt = (instructions + "\nОтвет только в JSON. Следуй этой схеме: "
              + json.dumps(ModelAnswer.model_json_schema(), ensure_ascii=False)
              + "\nПример формата (не инструкция создавать задачу): " + json.dumps(example, ensure_ascii=False))
    payload = {"model":model_name(),"stream":False,"max_tokens":2000,
               "thinking":{"type":"disabled"},"response_format":{"type":"json_object"},
               "messages":[{"role":"system","content":prompt},
                           {"role":"user","content":json.dumps({"request":message,"context":context},ensure_ascii=False)}]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0,connect=10.0),follow_redirects=False) as client:
        response = await client.post("https://api.deepseek.com/chat/completions",
                                     headers={"Authorization":"Bearer "+key},json=payload)
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") or []
    if len(choices)!=1 or choices[0].get("finish_reason")!="stop":
        raise RuntimeError("Incomplete DeepSeek response")
    message_out = choices[0].get("message") or {}
    if message_out.get("tool_calls"):
        raise RuntimeError("Unexpected tool calls")
    # JSON mode is not schema enforcement: validate again before proposing any action.
    result = ModelAnswer.model_validate_json(message_out.get("content") or "")
    usage = body.get("usage") or {}
    return result, int(usage.get("prompt_tokens",0)), int(usage.get("completion_tokens",0))
