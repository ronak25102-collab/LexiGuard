"""Recover numbered source sections without relying on selective LLM extraction.

The text remains verbatim. CUAD annotations and evaluation references are never
used here. Existing extraction supplies classifications, not clause contents.
"""

from __future__ import annotations

import re

from lexiguard.graph.schema import ClauseInfo, ContractData, CrossReference

# Atomic prefix prevents exponential backtracking on long source separator lines.
PREFIX = r"(?>[ \t]*(?:[>#*\-]+[ \t]*|<[^>]+>[ \t]*)*)"
NUMERIC = re.compile(
    rf"(?m)^{PREFIX}(?P<number>(?:§[ \t]*)?\d{{1,2}}(?:\.\d{{1,2}})*"
    r"(?:\([a-z]\))?)(?:[.)][ \t]*|[ \t]+)(?=[A-Za-z*\"'“‘])"
)
SECTION_HEADING = re.compile(rf"(?mi)^{PREFIX}(?:SECTION|ARTICLE)[ \t]+(\d{{1,2}})[:.][ \t]*")
INLINE = re.compile(r"(?<![\w.])(\d{1,2}(?:\.\d{1,2})+)[ \t]{2,}(?=[A-Za-z])")
LETTER = re.compile(rf"(?m)^{PREFIX}\(([a-z]|[ivx]{{2,5}})\)[ \t]+(?=\S)")
INLINE_LETTER = re.compile(r"(?<!\w)([a-z])\.[ \t]{2,}(?=[A-Za-z])")
EXHIBIT = re.compile(rf"(?mi)^{PREFIX}(?:EXHIBIT|SCHEDULE)[ \t]+([A-Z])\b")
ROMAN = re.compile(rf"(?m)^{PREFIX}([IVX]+)\.[ \t]+(?=[A-Za-z*])")
FRONT_MATTER = re.compile(rf"(?mi)^{PREFIX}(RECITALS|TERMS AND CONDITIONS|NOW[ ,\t]+THEREFORE)\b")
REFERENCE = re.compile(
    r"(?:sections?|paragraphs?|clauses?|§)[ \t]+"
    r"(\d{1,2}(?:\.\d{1,2})*(?:[ \t]*\([a-z]\))?)", re.I
)


def canonical_number(value: str) -> str:
    value = re.sub(r"^(?:section|paragraph|clause)\s+", "", value.strip(), flags=re.I)
    value = re.sub(r"\s*([().])\s*", r"\1", value)
    return re.sub(r"§\s*", "§ ", value).strip().rstrip(".")


def parse_source_sections(text: str) -> list[ClauseInfo]:
    events = [(m.start(), m.end(), "number", m.group("number")) for m in NUMERIC.finditer(text)]
    events += [(m.start(), m.end(), "number", m.group(1)) for m in SECTION_HEADING.finditer(text)]
    events += [(m.start(), m.end(), "number", m.group(1)) for m in INLINE.finditer(text)]
    events += [(m.start(), m.end(), "letter", m.group(1)) for m in LETTER.finditer(text)]
    events += [(m.start(), m.end(), "letter", m.group(1)) for m in INLINE_LETTER.finditer(text)]
    events += [(m.start(), m.end(), "exhibit", re.sub(r"<[^>]+>", "", m.group(0)).strip(" #*-\t\r"))
               for m in EXHIBIT.finditer(text)]
    events += [(m.start(), m.end(), "roman", m.group(1)) for m in ROMAN.finditer(text)]
    events += [(m.start(), m.end(), "front", m.group(1).upper())
               for m in FRONT_MATTER.finditer(text)]
    # The inline and line-start patterns can identify the same heading.
    events = sorted(set(events), key=lambda e: (e[0], e[2] != "number"))
    anchors, starts = [], set()
    namespace, numeric_parent, letter_parent = "", "", ""
    for index, (start, end, kind, value) in enumerate(events):
        if any(abs(start - prior) < 8 for prior in starts):
            continue
        if kind == "front":
            namespace = "Recitals" if value == "RECITALS" else ""
            numeric_parent, letter_parent = "", ""
            continue
        if kind == "exhibit":
            namespace, numeric_parent, letter_parent = value, "", ""
            number = value
        elif kind == "roman":
            namespace, numeric_parent, letter_parent = value, "", ""
            number = value
        elif kind == "number":
            numeric_parent, letter_parent = canonical_number(value), ""
            number = f"{namespace}. {numeric_parent}" if namespace else numeric_parent
        else:
            if not numeric_parent:
                continue
            next_letters = [e[3] for e in events[index + 1:index + 4] if e[2] == "letter"]
            roman_child = len(value) > 1 or (value == "i" and "ii" in next_letters)
            parent = letter_parent if roman_child and letter_parent else numeric_parent
            number = parent + f"({value})"
            if not roman_child:
                letter_parent = number
            number = f"{namespace}. {number}" if namespace else number
        starts.add(start)
        anchors.append((start, end, number, namespace))
    if not anchors:
        return []
    result = [ClauseInfo(number="Preamble", title="Contract introduction",
                         text=text[:anchors[0][0]].strip(), clause_type="Parties")]
    for index, (start, end, number, scope) in enumerate(anchors):
        finish = len(text)
        for other_start, _, other_number, other_scope in anchors[index + 1:]:
            if other_scope != scope or not (
                other_number.startswith(number + ".") or other_number.startswith(number + "(")
            ):
                finish = other_start
                break
        body = text[start:finish].strip()
        if not body:
            continue
        first_line = text[end:finish].split("\n", 1)[0].strip(" *#\t\r")
        title = first_line.split(". ", 1)[0][:100] or f"Section {number}"
        result.append(ClauseInfo(number=number, title=title, text=body, clause_type="Other"))
    # Repeated labels (for example numbered recitals) must not overwrite source text.
    merged = {}
    for clause in result:
        if clause.number in merged:
            prior = merged[clause.number]
            merged[clause.number] = prior.model_copy(update={"text": prior.text + "\n\n" + clause.text})
        elif clause.text:
            merged[clause.number] = clause
    return list(merged.values())


def resolve_reference(value: str, numbers: set[str], scope: str = "") -> str | None:
    number = canonical_number(value)
    candidates = [f"{scope}. {number}" if scope else number, number,
                  f"{scope}. § {number}" if scope else f"§ {number}"]
    for candidate in candidates:
        if candidate in numbers:
            return candidate
    # A reference to a lettered subparagraph may have only its containing section indexed.
    parent = re.sub(r"\([a-zivx]+\)$", "", number)
    if parent != number:
        return resolve_reference(parent, numbers, scope)
    return None


def enrich_from_source(contract: ContractData, text: str) -> ContractData:
    parsed = parse_source_sections(text)
    if not parsed:
        return contract
    existing = {canonical_number(c.number): c for c in contract.clauses}
    clauses = {}
    for clause in parsed:
        original = existing.get(clause.number)
        if original:
            clause = clause.model_copy(update={"title": original.title,
                                               "clause_type": original.clause_type})
        clauses[clause.number] = clause
    for number, clause in existing.items():
        if number not in clauses and not number.startswith("Recitals."):
            clauses[number] = clause
    numbers, edges = set(clauses), {}
    for edge in contract.cross_references:
        source = resolve_reference(edge.source_clause, numbers)
        target = resolve_reference(edge.target_clause, numbers)
        if source and target and source != target:
            candidate = CrossReference(source_clause=source, target_clause=target,
                                       relationship=edge.relationship)
            edges[(source, target)] = candidate
    for clause in parsed:
        scope = clause.number.split(". ", 1)[0] if ". " in clause.number else ""
        for match in REFERENCE.finditer(clause.text):
            target = resolve_reference(match.group(1), numbers, scope)
            if target and target != clause.number:
                edges.setdefault((clause.number, target), CrossReference(
                    source_clause=clause.number, target_clause=target, relationship="REFERENCES"))
    return contract.model_copy(update={"clauses": list(clauses.values()),
                                       "cross_references": list(edges.values())})
