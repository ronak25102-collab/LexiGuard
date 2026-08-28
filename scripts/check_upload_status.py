#!/usr/bin/env python3
"""Quick script to check why uploads are stuck."""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from lexiguard.config import get_settings, RAW_DATA_DIR, PARSED_DATA_DIR

def check_upload_status():
    """Check the status of recent uploads."""
    print("=" * 70)
    print("Upload Status Checker")
    print("=" * 70)
    
    # Check for uploaded PDFs
    raw_files = list(RAW_DATA_DIR.glob("*.pdf"))
    
    if not raw_files:
        print("\n❌ No uploaded files found in data/raw/")
        print("   → Have you uploaded a contract yet?")
        return
    
    print(f"\n✓ Found {len(raw_files)} uploaded PDF(s)")
    
    # Check each upload
    for pdf_file in sorted(raw_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        contract_id = pdf_file.stem
        print(f"\n" + "-" * 70)
        print(f"Contract ID: {contract_id}")
        print(f"File: {pdf_file.name}")
        print(f"Size: {pdf_file.stat().st_size:,} bytes")
        
        # Check status file
        status_file = PARSED_DATA_DIR / f"{contract_id}.status"
        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                
                stage = status_data.get('stage', 'unknown')
                progress = status_data.get('progress', 0)
                message = status_data.get('message', '')
                timestamp = status_data.get('timestamp', '')
                
                print(f"\nStatus: {stage.upper()}")
                print(f"Progress: {progress}%")
                print(f"Message: {message}")
                print(f"Last update: {timestamp}")
                
                if stage == "error":
                    print(f"\n❌ ERROR DETECTED!")
                    print(f"   Fix: {message}")
                elif stage == "completed":
                    print(f"\n✓ Processing completed successfully")
                elif progress <= 10:
                    print(f"\n⚠️  STUCK AT {progress}%!")
                    print(f"   This means background processing hasn't progressed.")
                    print(f"   → Check backend logs for errors")
                    print(f"   → Run: python scripts/test_config.py")
                else:
                    print(f"\n⏳ Processing in progress...")
                
            except json.JSONDecodeError as e:
                print(f"\n❌ Status file is corrupted: {e}")
                print(f"   Raw content: {status_file.read_text(encoding='utf-8')[:200]}")
            except Exception as e:
                print(f"\n❌ Error reading status: {e}")
        else:
            print(f"\n❌ NO STATUS FILE!")
            print(f"   Expected: {status_file}")
            print(f"   This means:")
            print(f"   1. Background task never started, OR")
            print(f"   2. Background task crashed immediately")
            print(f"\n   → Check backend logs for:")
            print(f"      - 'INFO: Starting processing for contract {contract_id}'")
            print(f"      - Any error messages after upload")
            print(f"\n   → Most likely cause: Missing API key in .env")
        
        # Check for parsed markdown
        parsed_file = PARSED_DATA_DIR / f"{contract_id}.md"
        if parsed_file.exists():
            size = parsed_file.stat().st_size
            print(f"\n✓ Parsed markdown exists ({size:,} bytes)")
        else:
            print(f"\n   (Parsed markdown not created yet)")
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    
    # Check if any are stuck
    stuck_count = 0
    for pdf_file in raw_files:
        contract_id = pdf_file.stem
        status_file = PARSED_DATA_DIR / f"{contract_id}.status"
        if not status_file.exists():
            stuck_count += 1
        elif status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                if status_data.get('progress', 0) <= 10 and status_data.get('stage') != 'error':
                    stuck_count += 1
            except:
                pass
    
    if stuck_count > 0:
        print(f"\n⚠️  {stuck_count} upload(s) appear stuck!")
        print("\n1. Check if backend is running:")
        print("   → You should see logs in the terminal")
        print("\n2. Verify configuration:")
        print("   → Run: python scripts/test_config.py")
        print("\n3. Check API key:")
        print("   → type .env | findstr API_KEY")
        print("   → Should show: OPENAI_API_KEY=sk-...")
        print("\n4. Check backend logs for errors")
        print("\n5. See DEBUG_UPLOAD.md for detailed troubleshooting")
    else:
        print("\n✓ All uploads appear to be processing normally")
        print("  (or completed/errored with clear status)")

if __name__ == "__main__":
    try:
        check_upload_status()
    except Exception as e:
        print(f"\n❌ Error running check: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
