"""Source ingestion must retain referenced clauses omitted by selective extraction."""

from lexiguard.graph.schema import ClauseInfo, ContractData, CrossReference
from lexiguard.ingestion.source_sections import enrich_from_source, parse_source_sections


def test_omitted_target_is_recovered_with_verbatim_source():
    text = "# Agreement\n\n1. Price\nPayment is subject to Section 2.\n\n2. Exception\nNo fee during downtime."
    contract = ContractData(source_file="example.md", title="Agreement", contract_type="Service",
        clauses=[ClauseInfo(number="1", title="Price", text="Payment is subject to Section 2.", clause_type="Payment")],
        cross_references=[CrossReference(source_clause="1", target_clause="2", relationship="MODIFIES")])
    result = enrich_from_source(contract, text)
    clauses = {c.number: c for c in result.clauses}
    assert clauses["2"].text == "2. Exception\nNo fee during downtime."
    assert any(e.source_clause == "1" and e.target_clause == "2" and e.relationship == "MODIFIES"
               for e in result.cross_references)


def test_lettered_children_and_whole_parent_are_indexed():
    text = "# Terms\n\n3. License\n(a) Grant. Access is allowed.\n(b) Exception. No sublicensing.\n\n4. Term\nFive years."
    clauses = {c.number: c.text for c in parse_source_sections(text)}
    assert "No sublicensing" in clauses["3"]
    assert "Access is allowed" in clauses["3(a)"]
    assert "No sublicensing" in clauses["3(b)"]
    assert "Five years" not in clauses["3"]


def test_inline_decimal_sections_do_not_merge_different_obligations():
    text = "1.       TERMS 1.1      Notice is required. 1.2      Consent is required.\n\n2. END\nDone."
    clauses = {c.number: c.text for c in parse_source_sections(text)}
    assert "Consent" not in clauses["1.1"]
    assert "Consent" in clauses["1.2"]


def test_exhibit_numbers_are_scoped_without_overwriting_main_sections():
    text = "1. Main term\nThirty days.\n\n# EXHIBIT A\n\n1. Schedule term\nSixty days."
    clauses = {c.number: c.text for c in parse_source_sections(text)}
    assert "Thirty days" in clauses["1"] and "Sixty days" not in clauses["1"]
    assert "Sixty days" in clauses["EXHIBIT A. 1"]


def test_markdown_heading_with_no_space_after_number_retains_child_scope():
    text = "# 1. DEFINITIONS\nA definition.\n# 2.TERM\n(a) Initial term. Five years.\n(b) Renewal. One year."
    clauses = {c.number: c.text for c in parse_source_sections(text)}
    assert "Five years" in clauses["2(a)"]
    assert "One year" in clauses["2(b)"]
    assert "2(b)" in clauses


def test_now_therefore_ends_recitals_before_the_numbered_agreement():
    text = "RECITALS\n1. Background.\n\nNOW, THEREFORE, the parties agree:\n\n1.       TERM\nOne year.\n2.       LAW\nMaryland."
    clauses = {c.number: c.text for c in parse_source_sections(text)}
    assert "Background" in clauses["Recitals. 1"]
    assert "One year" in clauses["1"]
    assert "Recitals. 2" not in clauses
def test_long_separator_lines_do_not_block_source_section_parsing():
    from lexiguard.ingestion.source_sections import parse_source_sections
    sections = parse_source_sections("-" * 300 + "\n1. Governing Law\nCalifornia governs.\n")
    assert any(s.number == "1" and "California" in s.text for s in sections)
