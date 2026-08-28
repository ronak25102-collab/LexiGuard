# Rate Limiting Quick Reference

## ✅ What's Protected

Your API key is now protected with:

1. **Chunk Limits** - Only process first N chunks of each contract (default: 3)
2. **Concurrent Limits** - Max N contracts processing simultaneously (default: 2)  
3. **Chunk Size** - Larger chunks = fewer API calls (default: 30,000 chars)

## 🎯 Default Settings (Recommended)

Add these to your `.env` file:

```bash
# Rate Limiting (already configured with safe defaults)
MAX_CHUNKS_PER_CONTRACT=3
MAX_CHUNK_SIZE=30000
MAX_CONCURRENT_UPLOADS=2
ENABLE_RATE_LIMITING=true
```

**With these defaults:**
- ✅ Protects against rate limits
- ✅ Keeps costs low (~3 API calls per contract)
- ✅ Still extracts key info (parties, main clauses, dates)
- ✅ Processes 2 contracts at once

## 💰 Cost Per Contract

| Setting | API Calls | Cost (gpt-4o-mini) |
|---------|-----------|-------------------|
| **Default (3 chunks)** | ~3 | ~$0.003 |
| Budget (2 chunks) | ~2 | ~$0.002 |
| Comprehensive (10 chunks) | ~10 | ~$0.010 |
| Unlimited | 5-20+ | $0.005-$0.020+ |

## 🚀 Quick Start

### 1. Check Current Settings
```bash
# Start server
python -m lexiguard.api.main

# Visit in browser
http://localhost:8000/config/validate
```

Look for the `rate_limiting` section:
```json
{
  "rate_limiting": {
    "enabled": true,
    "max_chunks_per_contract": 3,
    "estimated_cost_per_contract": "~3 API calls"
  }
}
```

### 2. Adjust if Needed

**If you're hitting rate limits:**
```bash
MAX_CONCURRENT_UPLOADS=1  # Process one at a time
```

**If extraction seems incomplete:**
```bash
MAX_CHUNKS_PER_CONTRACT=5  # Process more of each contract
```

**If costs are too high:**
```bash
MAX_CHUNKS_PER_CONTRACT=2  # Process less per contract
```

## 📊 Monitoring

Watch your backend logs when uploading:

```
INFO: Extracting entities from contract.pdf in 3 chunks (limit: 3)
INFO: Processing chunk 1/3...
INFO: Processing chunk 2/3...
INFO: Processing chunk 3/3...
```

**Warning to watch for:**
```
WARNING: Contract chunked into 5 parts, but only processing first 3 due to rate limiting
```
→ Increase `MAX_CHUNKS_PER_CONTRACT` if you need full extraction

## 🔧 Common Adjustments

### For OpenAI Free Tier (3 RPM limit)
```bash
MAX_CONCURRENT_UPLOADS=1
MAX_CHUNKS_PER_CONTRACT=2
```

### For OpenAI Paid Tier
```bash
MAX_CONCURRENT_UPLOADS=3
MAX_CHUNKS_PER_CONTRACT=5
```

### For Local LLM (no limits)
```bash
ENABLE_RATE_LIMITING=false
```

## ℹ️ Full Documentation

See [RATE_LIMITING.md](./RATE_LIMITING.md) for:
- Detailed explanations
- Cost calculations
- Troubleshooting
- Best practices

## 🆘 Need Help?

1. Check `/config/validate` endpoint
2. Review backend logs for chunk counts
3. See RATE_LIMITING.md for troubleshooting
