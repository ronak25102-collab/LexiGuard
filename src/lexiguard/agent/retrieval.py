"""Shared source-aware ranking and context selection for live and offline retrieval."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

TOPICS = (
    (r"non.?compet|compet(?:e|ing|ition)", ("non compete", "competing", "competition", "competitive")),
    (r"exclusiv", ("exclusive", "exclusivity", "restriction")),
    (r"revenue|profit.*shar|royalt", ("revenue", "profit", "sharing", "royalty")),
    (r"governing|jurisdiction|which.*law|what.*law", ("governing law", "jurisdiction", "laws")),
    (r"liability|liabilit|cap|consequential", ("liability", "limitation", "cap", "damages")),
    (r"indemn|infring|third.party", ("indemnification", "indemnify", "infringement")),
    (r"terminat|cure|without cause", ("termination", "terminate", "convenience", "cure")),
    (r"renew|expir", ("renewal", "renew", "expiration", "notice")),
    (r"initial.*term|commenc|effective date|how long.*agreement",
     ("initial", "term", "effective date", "begin", "commencement")),
    (r"invoice|payment|payable|when.*pay|\bfee\b", ("payment", "invoice", "payable", "fee")),
    (r"late|delay|penalt", ("delay", "late", "penalty", "liquidated damages", "exception")),
    (r"force.majeure|pandemic", ("force majeure", "pandemic", "relief", "notice")),
    (r"confiden|disclos", ("confidentiality", "disclosure", "confidential")),
    (r"assign|transfer", ("assignment", "assign", "transfer")),
    (r"audit|inspect.*record", ("audit", "inspection", "records")),
    (r"ownership|intellectual|license|licens|sublicens",
     ("ownership", "license", "sublicense", "rights")),
    (r"warrant|defect", ("warranty", "warranties", "defect", "remedy")),
    (r"written notice|notice requirement|hours", ("notice", "written", "hours")),
)
STOP = set("a an the of to in on for is are do does can must what which who how when "
           "under contract agreement section clause client vendor party parties this that "
           "and or if by with from it its as at be have has about my our their".split())


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z]+", text.lower()))


def topic_terms(question: str) -> list[str]:
    terms = [term for pattern, expansion in TOPICS
             if re.search(pattern, question.lower()) for term in expansion]
    if not terms:
        terms = [t for t in normalize(question).split() if t not in STOP and len(t) > 2]
    return list(dict.fromkeys(terms))


def search_query(question: str) -> str:
    """Keep legal topics separate from parties, already handled by contract scoping."""
    return " ".join(topic_terms(question)) or question


def source_aliases(contract: dict) -> list[str]:
    source = str(contract.get("source_file") or "")
    values = [str(contract.get("contract_id") or contract.get("id") or "")]
    if source:
        values += [source, Path(source).stem, hashlib.sha256(source.encode()).hexdigest()]
    return list(dict.fromkeys(v for v in values if v))


def lexical_score(question: str, doc: dict) -> float:
    terms = topic_terms(question)
    heading = normalize(" ".join(str(doc.get(k) or "") for k in ("title", "clause_type")))
    body = normalize(doc["text"])
    score = sum(8 * (normalize(term) in heading) + (normalize(term) in body) for term in terms)
    # Preserve specific conditions without rewarding repeated contract/party names.
    identity = normalize(" ".join(doc.get("parties", [])) + " " + str(doc.get("contract_title") or ""))
    detail = {word for word in normalize(question).split()
              if len(word) > 3 and word not in STOP and word not in identity.split()}
    score += 0.5 * sum(word in body.split() for word in detail)
    # Match numbered references generically; no expected answer/section is provided.
    sections = re.findall(r"(?:section|clause)\s+(\d+(?:\.\d+)*(?:\([a-z]\))?)",
                          question, re.I)
    if str(doc.get("section")) in sections:
        score += 12
    return float(score)


def doc_key(doc: dict) -> tuple:
    return (doc.get("contract_id"), doc.get("section"), normalize(doc["text"]))


def rank_candidates(question: str, docs: list[dict]) -> list[dict]:
    """Fuse heading/body rank with semantic rank; give a lexical bonus only to matches."""
    lexical = sorted(range(len(docs)), key=lambda i: -lexical_score(question, docs[i]))
    lexical_ranks = {idx: rank + 1 for rank, idx in enumerate(lexical)
                     if lexical_score(question, docs[idx]) > 0}
    def score(i):
        return 1 / (60 + i + 1) + (
            2 / (60 + lexical_ranks[i]) if i in lexical_ranks else 0
        )
    return [docs[i] for i in sorted(range(len(docs)), key=lambda i: -score(i))]


def render_context(doc: dict) -> str:
    header = []
    if doc.get("contract_title"):
        header.append("Contract: " + doc["contract_title"])
    if doc.get("parties"):
        header.append("Contract parties: " + ", ".join(doc["parties"]))
    if doc.get("section") or doc.get("title"):
        header.append(f"Section {doc.get('section') or 'unnumbered'}: {doc.get('title') or ''}")
    return "\n".join(header + [doc["text"]])


def source_window(question: str, doc: dict, budget: int) -> tuple[str, int]:
    """Choose a contiguous source excerpt; do not drop an obligation in a long clause's tail."""
    body = doc["text"]
    if len(body) <= budget:
        return body, 0
    if budget <= 0:
        return "", 0
    stride = max(1, budget // 2)
    starts = sorted(set([*range(0, max(1, len(body) - budget + 1), stride), len(body) - budget]))
    start = max(starts, key=lambda offset: lexical_score(
        question, {**doc, "title": "", "clause_type": "", "text": body[offset:offset + budget]}))
    return body[start:start + budget], start


def select_context(question: str, graph: list[dict], semantic: list[dict],
                   max_chars: int = 4500, max_docs: int = 3) -> list[dict]:
    """Reserve semantic evidence, include incoming overrides, and bound the final context."""
    graph, semantic = rank_candidates(question, graph), rank_candidates(question, semantic)
    chosen = []
    if graph:
        primary = next((d for d in graph if not d.get("linked_to")), graph[0])
        chosen.append(primary)
        linked = [d for d in graph if d.get("linked_to") == primary.get("section")
                  and d.get("contract_id") == primary.get("contract_id")]
        if linked:
            priority = {"EXCLUDES": 3, "SUPERSEDES": 3, "MODIFIES": 2, "REFERENCES": 1}
            linked.sort(key=lambda d: (-priority.get(d.get("relationship"), 0),
                                       -lexical_score(question, d)))
            chosen.append(linked[0])
    if semantic:
        chosen.append(semantic[0])
    chosen += graph + semantic
    unique, seen = [], set()
    for doc in chosen:
        key = doc_key(doc)
        if key not in seen:
            seen.add(key)
            unique.append(doc)
        if len(unique) == max_docs:
            break
    # Rank the selected evidence, rather than always placing a weak graph match first.
    unique = sorted(unique, key=lambda d: -lexical_score(question, d))
    remaining, result = max_chars, []
    for index, doc in enumerate(unique):
        # Reserve space for later evidence while allowing a long obligation to stay intact.
        reserve = sum(min(750, len(render_context(later))) for later in unique[index + 1:])
        budget = max(0, remaining - reserve)
        header = render_context({**doc, "text": ""})
        excerpt, start = source_window(question, doc, max(0, budget - len(header)))
        text = render_context({**doc, "text": excerpt})[:budget]
        if not text:
            break
        result.append({**doc, "source_text": doc["text"], "source_window_start": start,
                       "source_window_end": start + len(excerpt),
                       "text": text, "clause_number": str(doc.get("section") or "N/A"),
                       "clause_text": text})
        remaining -= len(text)
    return result
