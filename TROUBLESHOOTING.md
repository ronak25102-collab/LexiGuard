# LexiGuard Troubleshooting Guide

## Upload Stuck at "Processing..."

If your contract upload gets stuck at 10% with "File uploaded. Initializing processing...", follow these steps:

### Step 1: Validate Configuration

Run the configuration test script:

```bash
python scripts/test_config.py
```

This will check:
- ✓ LLM API key is configured
- ✓ Neo4j connection works
- ✓ Data directories exist

### Step 2: Check Your .env File

Make sure you have a `.env` file in the project root (copy from `.env.example`):

```bash
# Required settings
LLM_PROVIDER=openai  # or "google" or "nvidia"

# For OpenAI (recommended)
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4o-mini

# For Neo4j (get free at https://neo4j.com/cloud/aura-free/)
NEO4J_URI=neo4j+s://your-db-id.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password-here
```

### Step 3: Check Backend Logs

When running the FastAPI server, watch the console for errors:

```bash
cd src
python -m lexiguard.api.main
```

Look for:
- `ValueError: OPENAI_API_KEY is required` → Missing API key
- `Neo4j connection failed` → Wrong Neo4j credentials
- `Extraction failed` → API quota exceeded or invalid key

### Step 4: Test API Validation Endpoint

With the server running, visit:

```
http://localhost:8000/config/validate
```

This will show you exactly what's misconfigured.

### Step 5: Check Upload Status

You can check the detailed status of any upload by contract ID:

```
GET http://localhost:8000/contracts/{contract_id}/status
```

Or check the status file directly:
```bash
cat data/parsed/{contract_id}.status
```

## Common Issues

### Issue: "API key error"
**Solution:** 
1. Check your `.env` file has the correct API key
2. Verify `LLM_PROVIDER` matches the key you configured
3. Test your API key manually at the provider's website

### Issue: "Neo4j connection failed"
**Solution:**
1. Sign up for free Neo4j Aura: https://neo4j.com/cloud/aura-free/
2. Copy the connection URI (starts with `neo4j+s://`)
3. Use the generated password (save it during setup!)
4. Update your `.env` file

### Issue: "Processing timed out"
**Solution:**
1. The contract may be too large or complex
2. Try a smaller PDF file
3. Check your API rate limits
4. Increase timeout in `main.py` if needed

### Issue: "Extraction failed"
**Solution:**
1. Check your API quota/credits
2. Verify the PDF is readable (not scanned/image-based)
3. Try with a different PDF

## Getting Help

1. Run `python scripts/test_config.py` and share the output
2. Check the backend logs for detailed error messages
3. Visit `/config/validate` endpoint to see configuration status
4. Check the status file: `data/parsed/{contract_id}.status`

## Quick Reset

To clear all uploads and start fresh:

```bash
# Delete uploaded files
rm -rf data/raw/*.pdf
rm -rf data/parsed/*.md
rm -rf data/parsed/*.status

# Clear Neo4j graph (WARNING: deletes all data)
# Only do this in development!
```

Then restart your backend server.
