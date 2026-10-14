"""Build the one-page report with plain black text and no decorative elements."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/LexiGuard_live_ablation_brief.pdf"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    body = ParagraphStyle("body", fontName="Times-Roman", fontSize=10.5,
                          leading=13, textColor=colors.black, spaceAfter=7)
    heading = ParagraphStyle("heading", parent=body, fontName="Times-Bold",
                             fontSize=11, spaceBefore=4, spaceAfter=5)
    title = ParagraphStyle("title", parent=body, fontName="Times-Bold",
                           fontSize=14, leading=17, spaceAfter=7)
    cell = ParagraphStyle("cell", parent=body, fontSize=10, leading=12, spaceAfter=0)
    cell_head = ParagraphStyle("cell_head", parent=cell, fontName="Times-Bold")
    story = []

    def paragraph(text, style=body):
        story.append(Paragraph(text, style))

    paragraph("LexiGuard live retrieval ablation", title)
    paragraph("24 fresh CUAD questions, 6 public contracts, live Neo4j Aura")
    paragraph("CRAG restored context precision from 0.465 in the unprotected hybrid to 0.729, "
              "matching the vector baseline. Its faithfulness was 0.934 versus the baseline's "
              "0.959. This test does not establish an overall gain over vector retrieval.")

    paragraph("Ragas results", heading)
    rows = [
        ["Variant", "Faithfulness", "Context precision", "Factual F1"],
        ["Vector baseline", "0.959", "0.729", "0.515"],
        ["Hybrid without links", "0.918", "0.465", "0.400"],
        ["Hybrid with links, no CRAG", "0.941", "0.465", "0.380"],
        ["Hybrid + CRAG, evidence guard", "0.934", "0.729", "0.490"],
    ]
    table = Table([[Paragraph(text, cell_head if i == 0 else cell) for text in row]
                   for i, row in enumerate(rows)],
                  colWidths=[218, 86, 112, 79], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([table, Spacer(1, 8)])
    paragraph("Scores range from 0 to 1 and are case-macro means. All 24 cases are complete "
              "across all four variants for both primary metrics and supplementary factual F1. "
              "Raw F1 can penalize citations missing from short reference spans.")

    paragraph("Findings", heading)
    paragraph("The relevance node compares semantic-only and hybrid evidence before answering. "
              "It retained semantic evidence in 22 cases and selected hybrid evidence in 2. "
              "This addresses graph fragments displacing complete vector passages; it does not "
              "prove that graph retrieval adds value on this sample.")
    paragraph("The normal API recovered the audit/site-inspection, one-year renewal with "
              "30-day notice, and non-compete failures used during development. These are "
              "reported separately from the fresh cohort. A liability-cap case (F24) remained "
              "unretrieved and CRAG abstained after two rewrites; it remains in the headline results.")
    paragraph("Literal reference coverage in context was 80.5% for vector, 80.2% for guarded "
              "CRAG and 59.2% for unprotected hybrid. This is normalized word 5-gram recall, "
              "not semantic accuracy. No scope or stored source-window violations were found.")

    paragraph("Method and limitations", heading)
    paragraph("All variants used the same pinned generator, separate judge, embeddings, answer "
              "prompt and final budget: at most 3 excerpts and 4,500 characters. CRAG also "
              "inspects both alternatives (up to 9,000 characters) and can rewrite twice, so "
              "total inference cost is not equal across arms. Graph reads execute over verified "
              "TLS; offline graph replay is forbidden.")
    paragraph("Generator: CodeCraft gpt-5.6-luna (gateway-reported identity). Judge: NVIDIA "
              "nvidia/nemotron-3-super-120b-a12b. Embeddings: gemini-embedding-001, normalized "
              "768 dimensions. One run and six curated, positive-answer contracts are "
              "insufficient to establish generalization. The initial negative 26-case live "
              "pilot is retained in the package; its cohort is not pooled with these results.")

    paragraph("Supporting files and checks", heading)
    paragraph("The full report, frozen protocols and questions, exact measurement source, "
              "per-query scores, answers, executed Cypher and returned rows, source audits "
              "and cached responses are included in the full reproducibility package. One "
              "missing JSON comma was repaired without changing any judgment; the original "
              "response is preserved. Current source passed 62 tests and the frontend build. "
              "Aura has 30 source records and 1,351 clauses; Render redeployment remains separate.")
    paragraph("CUAD: Hendrycks, Burns, Chen and Ball, NeurIPS 2021. Original dataset repository: "
              "https://github.com/The-Atticus-Project/cuad. This is an independent application evaluation.")

    document = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=50, rightMargin=50,
                                 topMargin=40, bottomMargin=40,
                                 title="LexiGuard live retrieval ablation", author="Ronak Kumar")
    document.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    main()
