"""BM25 over a company's chunks (no embedding cost; good on financial terms). One index per company,
rebuilt when its chunk count changes."""
import re
import threading

from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Chunk, Document

STOP = set("""a an the of to in on for and or is are was were be been by with as at from that this it its we our
they their you your i he she them us will would should can could may might do does did has have had not no
what which who whom how why when where than then there here into over under about also very more most so such
please thank thanks sir madam yes okay ok just like one two""".split())
_cache: dict[int, tuple[int, BM25Okapi, list[int]]] = {}
_lock = threading.Lock()


def tokens(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?%?", text.lower())
    return [t for t in toks if t not in STOP and len(t) > 1]


def index(db: Session, company_id: int) -> tuple[BM25Okapi | None, list[int]]:
    n = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.company_id == company_id)) or 0
    with _lock:
        hit = _cache.get(company_id)
        if hit and hit[0] == n:
            return hit[1], hit[2]
    if n == 0:
        return None, []
    rows = db.execute(select(Chunk.id, Chunk.text).where(Chunk.company_id == company_id).order_by(Chunk.id)).all()
    ids = [r[0] for r in rows]
    bm = BM25Okapi([tokens(r[1]) for r in rows])
    with _lock:
        _cache[company_id] = (n, bm, ids)
    return bm, ids


def search(db: Session, company_id: int, query: str, k: int = 8, kinds: list[str] | None = None,
           doc_ids: list[int] | None = None) -> list[tuple[Chunk, float]]:
    bm, ids = index(db, company_id)
    if not bm:
        return []
    q = tokens(query)
    if not q:
        return []
    scores = bm.get_scores(q)
    ranked = sorted(zip(ids, scores), key=lambda x: -x[1])
    out = []
    for cid, s in ranked:
        if s <= 0 or len(out) >= k * 4:
            break
        out.append((cid, s))
    chunks = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_([c for c, _ in out]))).all()}
    docs = {}
    res = []
    for cid, s in out:
        c = chunks.get(cid)
        if not c:
            continue
        if kinds or doc_ids:
            d = docs.get(c.document_id) or db.get(Document, c.document_id)
            docs[c.document_id] = d
            if kinds and d.kind not in kinds:
                continue
            if doc_ids and d.id not in doc_ids:
                continue
        res.append((c, float(s)))
        if len(res) >= k:
            break
    return res
