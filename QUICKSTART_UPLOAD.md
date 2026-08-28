# Quick Start: Testing Contract Upload

Follow these steps to test the contract upload feature:

## 1. Validate Your Configuration

```bash
python scripts/test_config.py
```

If you see errors, fix them before proceeding:
- Missing API key? → Edit `.env` file
- Neo4j connection failed? → Check credentials in `.env`

## 2. Start the Backend Server

```bash
cd src
python -m lexiguard.api.main
```

You should see:
```
INFO:     Starting LexiGuard API...
INFO:     Neo4j connection verified.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 3. Start the Frontend (in a new terminal)

```bash
cd frontend
npm run dev
```

Visit: http://localhost:5173 (or the URL shown)

## 4. Upload a Contract

1. Click "Upload" in the navigation
2. Drag and drop a PDF contract
3. Watch the progress bar

**Expected Timeline:**
- 10% - File uploaded
- 25% - Converting PDF to text (15-30 seconds)
- 50% - Analyzing with AI (30-90 seconds, depends on contract size)
- 85% - Building knowledge graph (5-10 seconds)
- 100% - Complete!

## 5. Troubleshooting

### Upload stuck at 10%?

**Check backend logs** - you should see:
```
INFO: Starting processing for contract {id}
INFO: Parsing PDF: {file}
INFO: Successfully parsed PDF for {id}
INFO: Starting entity extraction for {id}
```

**If you see an error:**
- `API key validation failed` → Fix your `.env` file
- `Extraction failed` → Check API quota/credits
- `Neo4j connection failed` → Verify Neo4j credentials

### Check Upload Status Manually

Visit the validation endpoint:
```
http://localhost:8000/config/validate
```

Should return:
```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "api_key_configured": true,
  "neo4j_configured": true,
  "data_dirs_exist": {
    "raw": true,
    "parsed": true
  }
}
```

### Check Specific Contract Status

```
http://localhost:8000/contracts/{contract_id}/status
```

Replace `{contract_id}` with your actual contract ID (shown in the upload response).

## 6. View Results

Once complete (100%), go to:
- **Dashboard** - See the contract in the list
- **Query** - Ask questions about the contract
- **Evaluation** - Run accuracy tests

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Configuration error" on upload | Run `python scripts/test_config.py` |
| Stuck at 10% forever | Check backend logs, verify API key |
| "Processing timed out" | Try a smaller PDF file |
| "API quota exceeded" | Check your OpenAI/Google usage |
| Graph doesn't show data | Verify Neo4j connection |

## Need More Help?

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed debugging steps.
