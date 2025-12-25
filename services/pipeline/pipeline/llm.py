import httpx, os, datetime, json
from pathlib import Path

UPSTREAM = os.getenv("UPSTREAM_LLM_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
API_KEY = os.getenv("UPSTREAM_LLM_API_KEY", "your-dashscope-api-key")
MODEL = os.getenv("DEFAULT_MODEL", "qwen-plus")

# Use path relative to this module
_prompts_dir = Path(__file__).parent / "prompts"
grounded_prompt = (_prompts_dir / "grounded_expansion.txt").read_text()
rewrite_prompt = (_prompts_dir / "structured_rewrite.txt").read_text()


def chat(prompt, text):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    r = httpx.post(UPSTREAM, json={"model": MODEL, "messages": messages}, headers={"Authorization": f"Bearer {API_KEY}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def grounded_expand(text):
    return chat(grounded_prompt, text)


def structured_rewrite(expanded_text):
    md = chat(rewrite_prompt, expanded_text)
    now = datetime.datetime.utcnow().isoformat()
    ku_json = {
        "title": "Auto Generated KU",
        "summary": expanded_text[:200],
        "body_markdown": md,
        "sections": [],
        "tags": ["sales"],
        "glossary_terms": ["term1"],
        "source_refs": [],
        "evidence_map": {},
        "updated_at": now,
    }
    return ku_json, md
