# Rate Limiting & API Cost Control

## Overview

LexiGuard now includes built-in rate limiting to protect your API keys from hitting usage limits and to control costs.

## How It Works

### 1. **Chunk Limiting**
Large contracts are split into chunks for processing. Each chunk requires 1 API call to extract entities.

**Setting:** `MAX_CHUNKS_PER_CONTRACT=3` (default)

**Impact:**
- A contract with 100 pages might be split into 5 chunks
- With limit of 3, only first 3 chunks are processed (saves 2 API calls)
- You still get parties, key clauses, and important metadata from the first 60% of the contract

**When to adjust:**
- **Increase to 5-10** if you need complete extraction for longer contracts
- **Decrease to 1-2** if you're on a tight API budget and only need basic info
- **Set to `null`** to disable (process entire contract, no matter how long)

### 2. **Concurrent Upload Limiting**
Prevents multiple contracts from processing simultaneously.

**Setting:** `MAX_CONCURRENT_UPLOADS=2` (default)

**Impact:**
- Max 2 contracts can process at the same time
- 3rd upload waits in queue until a slot opens
- Prevents overwhelming your API with parallel requests

**When to adjust:**
- **Increase to 3-5** if you have high API rate limits
- **Decrease to 1** if you're getting rate limit errors
- Only applies to simultaneous uploads, not total uploads

### 3. **Chunk Size**
Maximum characters processed per API call.

**Setting:** `MAX_CHUNK_SIZE=30000` (default)

**Impact:**
- Larger chunks = fewer API calls (more cost-effective)
- Smaller chunks = more calls but better accuracy on complex documents
- 30,000 chars ≈ 12-15 pages of text

**When to adjust:**
- **Increase to 40000-50000** to reduce API calls (may reduce accuracy)
- **Decrease to 20000** if extractions are missing important clauses

## Configuration

Add to your `.env` file:

```bash
# Rate Limiting Settings
MAX_CHUNKS_PER_CONTRACT=3        # Limit chunks per contract
MAX_CHUNK_SIZE=30000              # Characters per chunk
MAX_CONCURRENT_UPLOADS=2          # Simultaneous processing limit
ENABLE_RATE_LIMITING=true         # Master switch
```

## Cost Estimation

### Example: Processing a 50-page contract

**With rate limiting (default):**
- Contract splits into 4 chunks
- Only 3 chunks processed (limit = 3)
- **Cost: 3 API calls** (~$0.003 with gpt-4o-mini)

**Without rate limiting:**
- All 4 chunks processed
- **Cost: 4 API calls** (~$0.004 with gpt-4o-mini)

**For 100 contracts:**
- With limiting: 300 API calls (~$0.30)
- Without limiting: 400+ API calls (~$0.40+)

### Recommended Settings by Usage

#### 💰 **Budget Mode** (Minimize costs)
```bash
MAX_CHUNKS_PER_CONTRACT=2
MAX_CHUNK_SIZE=35000
MAX_CONCURRENT_UPLOADS=1
```
- Extracts key info only
- Slowest processing
- Lowest cost (~2 API calls per contract)

#### ⚖️ **Balanced Mode** (Default)
```bash
MAX_CHUNKS_PER_CONTRACT=3
MAX_CHUNK_SIZE=30000
MAX_CONCURRENT_UPLOADS=2
```
- Good coverage of contract content
- Reasonable speed
- Moderate cost (~3 API calls per contract)

#### 🚀 **Comprehensive Mode** (Best accuracy)
```bash
MAX_CHUNKS_PER_CONTRACT=10
MAX_CHUNK_SIZE=25000
MAX_CONCURRENT_UPLOADS=3
```
- Full contract extraction
- Faster processing
- Higher cost (~5-10 API calls per contract)

#### 🔓 **Unlimited Mode** (No limits)
```bash
MAX_CHUNKS_PER_CONTRACT=null
MAX_CHUNK_SIZE=50000
MAX_CONCURRENT_UPLOADS=5
ENABLE_RATE_LIMITING=false
```
- Processes entire contract regardless of size
- Fastest processing
- Highest cost (variable, depends on contract size)

## Monitoring Usage

### Check Chunk Count in Logs

When processing, you'll see:
```
INFO: Extracting entities from contract.pdf in 3 chunks (limit: 3)
INFO: Processing chunk 1/3...
INFO: Processing chunk 2/3...
INFO: Processing chunk 3/3...
```

If you see:
```
WARNING: Contract chunked into 5 parts, but only processing first 3 due to rate limiting
```

This means content was truncated. Increase `MAX_CHUNKS_PER_CONTRACT` if needed.

### Calculate Monthly Costs

**Formula:**
```
Monthly Cost = (Contracts per month) × (Avg chunks per contract) × (Cost per API call)
```

**Example with gpt-4o-mini ($0.001 per call):**
- 50 contracts/month
- 3 chunks average
- 50 × 3 × $0.001 = **$0.15/month**

**With no rate limiting (~5 chunks):**
- 50 × 5 × $0.001 = **$0.25/month**

## API Rate Limits by Provider

### OpenAI (Free Tier)
- **Requests:** 3 RPM (requests per minute)
- **Tokens:** 40,000 TPM (tokens per minute)
- **Recommended:** `MAX_CONCURRENT_UPLOADS=1`

### OpenAI (Tier 1)
- **Requests:** 500 RPM
- **Tokens:** 200,000 TPM
- **Recommended:** `MAX_CONCURRENT_UPLOADS=3`

### Google Gemini (Free)
- **Requests:** 15 RPM
- **Recommended:** `MAX_CONCURRENT_UPLOADS=2`

### NVIDIA NIM (Free)
- **Requests:** 1,000 RPM
- **Recommended:** `MAX_CONCURRENT_UPLOADS=5`

## Disabling Rate Limiting

To disable all rate limiting (process entire contracts, no queuing):

```bash
ENABLE_RATE_LIMITING=false
```

**Use cases:**
- You have high API rate limits
- You're using a local LLM
- You need complete extraction regardless of cost

## Troubleshooting

### "Rate limit exceeded" errors

**Solutions:**
1. Decrease `MAX_CONCURRENT_UPLOADS` to 1
2. Wait a few minutes between uploads
3. Upgrade your API tier
4. Reduce `MAX_CHUNKS_PER_CONTRACT`

### Extraction seems incomplete

**Solutions:**
1. Increase `MAX_CHUNKS_PER_CONTRACT` to 5-10
2. Check logs to see if chunks were truncated
3. Verify the PDF is readable (not image-based)

### Processing is too slow

**Solutions:**
1. Increase `MAX_CONCURRENT_UPLOADS` to 3-5
2. Increase `MAX_CHUNK_SIZE` to 40000
3. Ensure your API key has high rate limits

## Best Practices

1. **Start with defaults** - They work well for most use cases
2. **Monitor logs** - Watch for truncation warnings
3. **Test incrementally** - Upload 1-2 contracts, then adjust settings
4. **Track costs** - Check your API provider's usage dashboard
5. **Upgrade if needed** - If hitting limits often, consider higher API tier

## Need Help?

Check the logs for detailed processing information:
```bash
# Watch backend logs
python -m lexiguard.api.main
```

Look for:
- Chunk counts: "Extracting entities in N chunks (limit: X)"
- Truncation warnings: "Only processing first N chunks"
- Rate limit errors: "quota exceeded" or "rate limit"
