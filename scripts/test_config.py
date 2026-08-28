#!/usr/bin/env python3
"""Quick configuration test script to validate LexiGuard setup."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from lexiguard.config import get_settings, RAW_DATA_DIR, PARSED_DATA_DIR
from lexiguard.graph.neo4j_client import Neo4jClient

def test_configuration():
    """Test all configuration requirements."""
    print("=" * 60)
    print("LexiGuard Configuration Test")
    print("=" * 60)
    
    settings = get_settings()
    all_ok = True
    
    # Test 1: LLM Provider Configuration
    print(f"\n1. LLM Provider: {settings.llm_provider}")
    try:
        api_key = settings.active_api_key
        print(f"   ✓ API key configured for {settings.llm_provider}")
        print(f"   ✓ Model: {settings.active_model}")
    except ValueError as e:
        print(f"   ✗ API key error: {e}")
        print(f"   → Check your .env file and set the appropriate API key")
        all_ok = False
    
    # Test 2: Neo4j Configuration
    print(f"\n2. Neo4j Database")
    print(f"   URI: {settings.neo4j_uri}")
    print(f"   Username: {settings.neo4j_username}")
    try:
        with Neo4jClient() as client:
            if client.verify_connection():
                print("   ✓ Neo4j connection successful")
            else:
                print("   ✗ Neo4j connection failed")
                print("   → Check NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env")
                all_ok = False
    except Exception as e:
        print(f"   ✗ Neo4j error: {e}")
        print("   → Verify Neo4j is running and credentials are correct")
        all_ok = False
    
    # Test 3: Data Directories
    print(f"\n3. Data Directories")
    print(f"   Raw data: {RAW_DATA_DIR}")
    if RAW_DATA_DIR.exists():
        print(f"   ✓ Raw data directory exists")
    else:
        print(f"   → Creating raw data directory...")
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Created")
    
    print(f"   Parsed data: {PARSED_DATA_DIR}")
    if PARSED_DATA_DIR.exists():
        print(f"   ✓ Parsed data directory exists")
    else:
        print(f"   → Creating parsed data directory...")
        PARSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Created")
    
    # Test 4: Rate Limiting Configuration
    print(f"\n4. Rate Limiting & Cost Control")
    print(f"   Enabled: {settings.enable_rate_limiting}")
    print(f"   Max chunks per contract: {settings.max_chunks_per_contract}")
    print(f"   Max concurrent uploads: {settings.max_concurrent_uploads}")
    print(f"   Estimated cost per contract: ~{settings.max_chunks_per_contract} API calls")
    if settings.enable_rate_limiting:
        print(f"   ✓ Rate limiting active (protects your API key)")
    else:
        print(f"   ⚠️  Rate limiting disabled (may hit API limits)")
    
    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All configuration tests passed!")
        print("\nYour LexiGuard setup is ready to use.")
    else:
        print("✗ Configuration errors detected!")
        print("\nPlease fix the issues above before running the application.")
    print("=" * 60)
    
    return all_ok

if __name__ == "__main__":
    success = test_configuration()
    sys.exit(0 if success else 1)
