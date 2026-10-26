import json, re
from pathlib import Path
import numpy as np
import pymupdf
from sentence_transformers import SentenceTransformer

DOCS, OUT = Path("docs"), Path("index")
OUT.mkdir(exist_ok=True)

def chunk_file(path):
    chunks, heading, buf = [], "(intro)", []
    def flush():
        text = "\n".join(buf).strip()
        if len(text) > 20:
            chunks.append({"source": path.name, "section": heading, "text": text})
        buf.clear()
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^#{1,4}\s", line):
            flush()
            heading = line.lstrip("#").strip()
        else:
            buf.append(line)
    flush()
    return chunks

def chunk_pdf(path, max_chars=1000):
    chunks = []
    with pymupdf.open(path) as pdf:
        for page_no, page in enumerate(pdf, start=1):
            blocks = page.get_text("blocks", sort=True)
            paras = []
            for b in blocks:
                if b[6] != 0:          # skip image blocks
                    continue
                text = re.sub(r"\s+", " ", b[4]).strip()
                if len(text) < 15 or "...." in text:   # skip page numbers and table-of-contents lines
                    continue
                paras.append(text)
            buf = ""
            for p in paras:
                if buf and len(buf) + len(p) > max_chars:
                    chunks.append({"source": path.name, "section": f"page {page_no}", "text": buf})
                    buf = ""
                buf = f"{buf} {p}".strip()
            if len(buf) > 40:
                chunks.append({"source": path.name, "section": f"page {page_no}", "text": buf})
    return chunks

chunks = []
for f in sorted(DOCS.iterdir()):
    if f.suffix.lower() == ".md":
        chunks += chunk_file(f)
    elif f.suffix.lower() == ".pdf":
        chunks += chunk_pdf(f)
for i, c in enumerate(chunks):
    slug = re.sub(r"[^a-z0-9]+", "-", Path(c["source"]).stem.lower()).strip("-")
    c["id"] = f"{slug}-{i:03d}"

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
emb = model.encode([f"{c['section']}\n{c['text']}" for c in chunks],
                   normalize_embeddings=True)
np.save(OUT / "embeddings.npy", emb)
json.dump(chunks, open(OUT / "chunks.json", "w", encoding="utf-8"), indent=1)
print(f"Indexed {len(chunks)} chunks")
