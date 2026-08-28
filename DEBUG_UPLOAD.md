# Debugging Upload Stuck at 10%

## What's Happening

Your upload is stuck at 10% "Processing..." which means:
- ✅ File uploaded successfully
- ❌ Background processing hasn't started or crashed immediately

## Root Cause Check

### Step 1: Is the Backend Running?

Open your backend terminal. You should see logs like:
```
INFO: Starting LexiGuard API...
INFO: Neo4j connection verified.
INFO: Uvicorn running on http://0.0.0.0:8000
```

**If you don't see this:**
1. Backend crashed or wasn't started
2. Start it with: `python -m lexiguard.api.main` (from `src` directory)

### Step 2: Check for Error Logs

After uploading, you should see in backend logs:
```
INFO: Processing upload: {filename} -> {contract_id}
INFO: Saved uploaded file: {path}
INFO: Queuing background task for {contract_id}
INFO: Background task queued successfully
INFO: Acquired processing slot for {contract_id}
INFO: Starting processing for contract {contract_id}
```

**If logs stop after "Queuing background task":**
- Background task is failing to start
- Most likely: Missing or invalid API key

**If you see an error like:**
```
ValueError: OPENAI_API_KEY is required when LLM_PROVIDER=openai
```
→ Your `.env` file is missing the API key

### Step 3: Check Status File

Look in `data/parsed/` for a file named `{contract_id}.status`:

```bash
# Windows
type data\parsed\*_6e6095c1.status

# Or find your contract ID from the upload response
```

**If file doesn't exist:**
- Background task crashed before creating status file
- Check backend logs for errors

**If file exists and shows error:**
```json
{
  "stage": "error",
  "progress": 0,
  "message": "Configuration error: OPENAI_API_KEY is required..."
}
```
→ Fix the error shown in the message

### Step 4: Check Raw Upload

Look in `data/raw/` - your PDF should be there:

```bash
dir data\raw\*.pdf
```

**If PDF exists but no status file:**
- Background task never started
- API key issue or configuration problem

## Most Common Causes

### 1. Missing API Key (90% of cases)

**Check your `.env` file:**
```bash
type .env
```

Should contain:
```bash
OPENAI_API_KEY=sk-proj-...your-actual-key...
LLM_PROVIDER=openai
```

**If missing:**
1. Copy `.env.example` to `.env`
2. Add your real API key
3. Restart backend server

### 2. Backend Crashed

**Restart the backend:**
```bash
cd src
python -m lexiguard.api.main
```

Watch for startup errors.

### 3. Wrong Working Directory

**Backend must run from `src` folder:**
```bash
# Wrong - won't find modules
python src/lexiguard/api/main.py

# Right - can import lexiguard
cd src
python -m lexiguard.api.main
```

### 4. Virtual Environment Not Activated

**Activate venv first:**
```bash
# Windows
.venv\Scripts\activate

# Then run backend
cd src
python -m lexiguard.api.main
```

## Quick Diagnostic Commands

### Check Config Validation
```bash
# With backend running, visit:
http://localhost:8000/config/validate
```

Should show:
```json
{
  "api_key_configured": true,
  "neo4j_configured": true
}
```

If `false`, that's your problem.

### Run Config Test Script
```bash
python scripts/test_config.py
```

Will tell you exactly what's wrong.

### Check Contract Status Manually
```bash
# Get contract ID from upload response, then:
http://localhost:8000/contracts/{contract_id}/status
```

Look for `"status": "error"` and check the `"message"` field.

## Step-by-Step Fix

1. **Stop everything** (Ctrl+C in both terminals)

2. **Verify `.env` file has API key:**
   ```bash
   type .env | findstr API_KEY
   ```
   Should output: `OPENAI_API_KEY=sk-proj-...`

3. **Test configuration:**
   ```bash
   python scripts/test_config.py
   ```
   Fix any errors shown.

4. **Start backend fresh:**
   ```bash
   cd src
   python -m lexiguard.api.main
   ```
   Watch for errors.

5. **Try upload again**

6. **Watch backend logs** - should show processing steps

## If Still Stuck

### Check This Exact Sequence in Backend Logs:

When you upload, you MUST see:
```
1. INFO: Processing upload: file.pdf -> contract_abc123
2. INFO: Saved uploaded file: (path) (73440 bytes)
3. INFO: Queuing background task for contract_abc123
4. INFO: Background task queued successfully
5. INFO: Acquired processing slot for contract_abc123
6. INFO: Starting processing for contract contract_abc123
7. INFO: Status update [contract_abc123]: uploading (10%) - File uploaded successfully
8. INFO: Parsing PDF: (path)
```

**If logs stop at line 4:**
- Semaphore issue (shouldn't happen)

**If logs stop at line 7:**
- Status file write failed
- Check `data/parsed/` exists and is writable

**If logs stop at line 8:**
- PDF parsing starting but failing
- Check the next error message

**If you see:**
```
ERROR: API key validation failed
```
→ Fix your `.env` file

**If you see:**
```
ERROR: PDF parsing failed
```
→ PDF may be corrupted or image-based (not text)

## Get Help

If none of this works:

1. Copy your **exact backend logs** (from startup to upload)
2. Copy the output of `python scripts/test_config.py`
3. Copy the output of `http://localhost:8000/config/validate`
4. Check if `data/parsed/{contract_id}.status` exists and what it says

This will show exactly where it's failing.
