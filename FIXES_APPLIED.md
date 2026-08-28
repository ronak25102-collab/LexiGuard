# Upload Processing Fixes Applied

## Issue
Contract uploads were getting stuck at 10% "Processing..." with no progress.

## Root Causes Identified

1. **Async/Sync Mismatch**: The `process_uploaded_contract` async function was calling synchronous blocking functions (`parse_contract`, `extract_contract_entities`, `graph_builder.build_contract_graph`) directly without awaiting them in a thread pool, blocking the FastAPI event loop.

2. **Silent Failures**: If parsing or extraction failed early, the status file wouldn't update beyond 10%, leaving users with no feedback.

3. **Missing API Key Validation**: The server would accept uploads even if the LLM API key wasn't configured, causing failures deep in the pipeline.

4. **Poor Error Messages**: Generic exceptions didn't provide actionable information about what went wrong.

## Fixes Applied

### 1. Fixed Async/Sync Issues in `main.py`
**File:** `src/lexiguard/api/main.py`

**Changes:**
- Wrapped all synchronous I/O operations in `asyncio.to_thread()`:
  ```python
  # Before
  markdown_text = parse_contract(file_path)
  
  # After
  markdown_text = await asyncio.to_thread(parse_contract, file_path)
  ```

- Applied to:
  - `parse_contract()` - PDF parsing
  - `file.write_text()` / `file.write_bytes()` - File I/O
  - `extract_contract_entities()` - LLM extraction
  - `graph_builder.build_contract_graph()` - Neo4j operations

### 2. Enhanced Error Handling
**Added granular try/catch blocks:**

```python
# Parse stage
try:
    markdown_text = await asyncio.to_thread(parse_contract, file_path)
    logger.info(f"Successfully parsed PDF, length: {len(markdown_text)} chars")
except Exception as e:
    logger.error(f"PDF parsing failed: {e}", exc_info=True)
    update_status("error", 0, f"Failed to parse PDF: {str(e)}")
    return  # Exit early with clear error
```

**Added specific error detection:**
- API key errors → "Configuration error: Please check your .env file"
- Rate limit errors → "API quota exceeded. Please try again later"
- Timeout errors → "Processing timed out. Contract may be too complex"

### 3. Added Pre-Upload Validation

**In `/upload` endpoint:**
```python
# Validate configuration before accepting upload
try:
    settings = get_settings()
    _ = settings.active_api_key  # Raises ValueError if missing
    logger.info(f"Using LLM provider: {settings.llm_provider}")
except ValueError as e:
    raise HTTPException(
        status_code=503,
        detail=f"Server configuration error: {str(e)}"
    )
```

Now uploads are rejected immediately if API key is missing, instead of failing silently after uploading.

### 4. Improved Status Updates

**Enhanced `update_status()` function:**
```python
def update_status(stage: str, progress: int, message: str = ""):
    try:
        status_data = {
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        PARSED_DATA_DIR.mkdir(parents=True, exist_ok=True)  # Ensure dir exists
        status_file.write_text(json.dumps(status_data), encoding="utf-8")
        logger.info(f"Status update [{contract_id}]: {stage} ({progress}%) - {message}")
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
```

### 5. Added Validation Endpoint

**New endpoint:** `GET /config/validate`

Returns:
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

Allows debugging without looking at logs or .env files.

### 6. Added Configuration Test Script

**New file:** `scripts/test_config.py`

Run with: `python scripts/test_config.py`

Tests:
- ✓ LLM API key is configured
- ✓ Neo4j connection works
- ✓ Data directories exist
- ✓ Model configuration is valid

### 7. Enhanced Logging

**Added structured logging:**
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

All processing steps now log clearly:
- Contract ID included in every log message
- Success/failure explicitly stated
- Error details with full tracebacks

### 8. Documentation

**Created:**
- `TROUBLESHOOTING.md` - Step-by-step debugging guide
- `QUICKSTART_UPLOAD.md` - Testing instructions
- `FIXES_APPLIED.md` - This document

## Testing the Fixes

### Step 1: Validate Configuration
```bash
python scripts/test_config.py
```

### Step 2: Check Validation Endpoint
```bash
# Start server
python -m lexiguard.api.main

# In browser or curl
http://localhost:8000/config/validate
```

### Step 3: Test Upload
1. Upload a contract via the UI
2. Watch backend console for detailed logs
3. Check status updates in real-time

### Step 4: Debug Issues
If upload still fails:
1. Check backend logs for specific error
2. Visit `/config/validate` to see what's misconfigured
3. Check status file: `data/parsed/{contract_id}.status`
4. See TROUBLESHOOTING.md for solutions

## Expected Behavior Now

### Upload Flow:
1. **10%** - "File uploaded successfully" (instant)
2. **25%** - "Converting PDF to text..." (15-30 sec)
   - Logs: "Parsing PDF: {path}"
   - Logs: "Successfully parsed PDF, length: X chars"
3. **50%** - "Analyzing contract with AI..." (30-90 sec)
   - Logs: "Starting entity extraction"
   - Logs: "Processing chunk 1/N..."
   - Logs: "Successfully extracted X clauses"
4. **85%** - "Building knowledge graph..." (5-10 sec)
   - Logs: "Building knowledge graph"
   - Logs: "Successfully built graph"
5. **100%** - "Processing complete!" ✓

### Error Handling:
- API key missing → 503 error on upload, immediate feedback
- Parsing fails → Status shows "Failed to parse PDF: {reason}"
- Extraction fails → Status shows "Extraction failed: {reason}"
- Graph building fails → Status shows "Failed to build knowledge graph: {reason}"

## What to Check If Still Stuck

1. **Backend logs** - Should see detailed progress:
   ```
   INFO: Starting processing for contract {id}
   INFO: Parsing PDF: {file}
   INFO: Successfully parsed PDF for {id}, length: 12345 chars
   INFO: Starting entity extraction for {id}
   INFO: Processing chunk 1/2...
   INFO: Successfully extracted 15 clauses from {id}
   INFO: Building knowledge graph for {id}
   INFO: Successfully processed contract {id}
   ```

2. **Status file** - `data/parsed/{contract_id}.status`:
   ```json
   {
     "stage": "extracting",
     "progress": 50,
     "message": "Analyzing contract with AI...",
     "timestamp": "2024-01-15T10:30:00"
   }
   ```

3. **API validation** - `/config/validate` should show all true

4. **.env file** - Must have valid API key for your chosen provider

## Files Modified

- `src/lexiguard/api/main.py` - Main fixes applied
- `scripts/test_config.py` - New validation script
- `TROUBLESHOOTING.md` - New debugging guide
- `QUICKSTART_UPLOAD.md` - New testing guide
- `FIXES_APPLIED.md` - This document

## Next Steps

1. Restart your backend server:
   ```bash
   cd src
   python -m lexiguard.api.main
   ```

2. Run configuration test:
   ```bash
   python scripts/test_config.py
   ```

3. Try uploading a contract again

4. Monitor backend logs for detailed progress

5. If issues persist, check TROUBLESHOOTING.md
