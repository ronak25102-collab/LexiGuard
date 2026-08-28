# Quick Fix for Upload - Skip LLM Extraction

The upload system is working, but the Gemini API extraction is taking too long (5+ minutes) or timing out.

## Immediate Solution

For demonstration purposes, we can skip the heavy LLM extraction and just:
1. Parse the PDF ✅ (works fast)
2. Save the markdown ✅ (works)
3. Create a basic contract node ✅ (skip detailed extraction)
4. Mark as "completed" ✅

This would make uploads complete in ~10 seconds instead of 5+ minutes.

## To implement:

Replace the extraction step in `process_uploaded_contract` with a simple mock that creates a basic contract node with:
- Title (from filename)
- Type: "Unknown"
- One basic clause with the full text
- Status: Completed

This makes the system usable for demo while we optimize the extraction.

## Long-term solutions:

1. **Switch to faster model** - Use GPT-4o-mini or Claude Haiku
2. **Parallel processing** - Process chunks in parallel
3. **Simpler extraction** - Extract only title + parties, skip detailed clauses
4. **Job queue** - Use Celery with Redis for proper background processing
5. **Caching** - Cache extraction results
