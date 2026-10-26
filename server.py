import json
import os

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from fastembed import TextEmbedding
from pydantic import BaseModel

load_dotenv()  # reads OPENAI_API_KEY, OPENAI_MODEL, MIN_SCORE from .env in this folder

MIN_SCORE = float(os.getenv("MIN_SCORE", "0.5"))   # below this, we refuse without calling the LLM
TOP_K = 4
NOT_DOCUMENTED = "That isn't covered in the project documentation."

app = FastAPI()
model = TextEmbedding("BAAI/bge-small-en-v1.5")
emb = np.load("index/embeddings.npy")
chunks = json.load(open("index/chunks.json", encoding="utf-8"))
PREFIX = "Represent this sentence for searching relevant passages: "

_client = None


def llm():
    global _client
    if _client is None:
        _client = OpenAI()  # uses OPENAI_API_KEY from the environment
    return _client


class Ask(BaseModel):
    question: str
    top_k: int = 3


def retrieve(question: str, k: int):
    q = next(iter(model.embed([PREFIX + question])))
    scores = emb @ q
    top = np.argsort(-scores)[:k]
    return [{**chunks[i], "score": float(scores[i])} for i in top]


@app.post("/context")
def context(req: Ask):
    return {"results": retrieve(req.question, req.top_k)}


SYSTEM_PROMPT = """You are a roofing training assistant inside a VR training app.
Answer ONLY from the numbered passages provided. Never use outside knowledge.
Rules:
- If the passages do not clearly answer the question, set status to "not_documented".
- If the question is too vague to answer (for example it could mean several things), set status to "clarify" and put ONE short clarifying question in "answer".
- Otherwise set status to "answered" and give a short answer (1-3 sentences) that is easy to read aloud. Keep numbers and units exactly as written in the passages.
- List the ids of the passages you used in "source_ids". Only use ids that appear in the passages.
Respond with JSON only, in this exact shape:
{"status": "answered" | "not_documented" | "clarify", "answer": "...", "source_ids": ["..."]}"""


def refusal(top_score: float):
    return {"status": "not_documented", "answer": NOT_DOCUMENTED, "sources": [], "top_score": top_score}


@app.post("/ask")
def ask(req: Ask):
    model_name = os.getenv("OPENAI_MODEL")
    if not model_name or not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(500, "Set OPENAI_API_KEY and OPENAI_MODEL in the .env file.")

    found = retrieve(req.question, TOP_K)
    top_score = found[0]["score"] if found else 0.0

    # Gate 1: nothing relevant retrieved -> refuse without calling the LLM.
    if top_score < MIN_SCORE:
        return refusal(top_score)

    passages = "\n\n".join(
        f"[{c['id']}] ({c['source']}, {c['section']})\n{c['text']}" for c in found
    )
    user_msg = f"Passages:\n{passages}\n\nQuestion: {req.question}"

    try:
        resp = llm().chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            timeout=30,
        )
        out = json.loads(resp.choices[0].message.content)
    except Exception as e:
        raise HTTPException(502, f"Answer model failed: {e}")

    status = out.get("status")
    answer = str(out.get("answer", "")).strip()

    # Gate 2: only keep citations that were really retrieved.
    by_id = {c["id"]: c for c in found}
    ids = [i for i in out.get("source_ids", []) if i in by_id]

    if status == "answered" and (not ids or not answer):
        return refusal(top_score)   # no valid citation -> don't trust it
    if status not in ("answered", "clarify"):
        return refusal(top_score)

    sources = [
        {"id": i, "source": by_id[i]["source"], "section": by_id[i]["section"], "score": by_id[i]["score"]}
        for i in ids
    ]
    return {"status": status, "answer": answer, "sources": sources, "top_score": top_score}
