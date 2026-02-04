#!/usr/bin/env python3
"""
Test script to verify concurrency and data loss fixes
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_atomic_writes():
    """Test that atomic writes work correctly"""
    print("🧪 Testing atomic file writes...")
    
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        test_file = Path(f.name)
        initial_data = [{"id": 1, "value": "test"}]
        json.dump(initial_data, f)
    
    try:
        # Simulate atomic write
        new_data = [{"id": 1, "value": "updated"}, {"id": 2, "value": "new"}]
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=test_file.parent,
            delete=False,
            suffix='.tmp'
        ) as tmp:
            temp_path = tmp.name
            json.dump(new_data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        
        # Atomic rename
        os.rename(temp_path, test_file)
        
        # Verify content
        with open(test_file, 'r') as f:
            result = json.load(f)
        
        assert len(result) == 2, f"Expected 2 records, got {len(result)}"
        assert result[0]["value"] == "updated", "First record not updated"
        assert result[1]["value"] == "new", "Second record not added"
        
        print("   ✅ Atomic writes work correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if test_file.exists():
            os.unlink(test_file)


async def test_data_manager_locking():
    """Test that DataManager uses proper locking"""
    print("🧪 Testing DataManager locking...")
    
    # Save original DATA_FILE setting
    original_data_file = None
    test_file = None
    
    try:
        # Import after dependencies are installed
        import app
        from app import DataManager
        
        # Create a temporary test file to avoid modifying the real data
        test_file = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='_test_data_manager.json',
            dir='.'
        )
        test_data = [
            {"id": 1, "Status": "Pending"},
            {"id": 2, "Status": "done"},
            {"id": 3, "Status": "Pending"}
        ]
        json.dump(test_data, test_file)
        test_file.close()
        
        # Temporarily override the DATA_FILE setting
        original_data_file = app.DATA_FILE
        app.DATA_FILE = Path(test_file.name)
        
        # Ensure parent folder exists
        app.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # Create DataManager
        dm = DataManager()
        await dm.initialize()
        
        # Test that stats method is async and uses locking
        stats = await dm.get_stats()
        assert stats["total_records"] == 3, f"Expected 3 records, got {stats['total_records']}"
        assert stats["by_status"]["Pending"] == 2, "Expected 2 pending records"
        
        # Test update_record
        result = await dm.update_record(0, {"Status": "done"}, username="test")
        assert result["status"] == "success", "Update failed"
        
        # Verify stats updated
        stats = await dm.get_stats()
        assert stats["by_status"]["done"] == 2, "Expected 2 done records after update"
        assert stats["by_status"]["Pending"] == 1, "Expected 1 pending record after update"
        
        print("   ✅ DataManager locking works correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original DATA_FILE
        if original_data_file:
            app.DATA_FILE = original_data_file
        
        # Clean up test file
        if test_file and os.path.exists(test_file.name):
            os.unlink(test_file.name)
            # Also clean up lock file
            lock_file = test_file.name + '.lock'
            if os.path.exists(lock_file):
                os.unlink(lock_file)


async def test_version_conflict_detection():
    """Test that version conflicts are detected atomically"""
    print("🧪 Testing atomic version conflict detection...")
    
    # Save original DATA_FILE setting
    original_data_file = None
    test_file = None
    
    try:
        import app
        from app import DataManager
        
        # Create a temporary test file
        test_file = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='_test_version.json',
            dir='.'
        )
        test_data = [{"id": 1, "value": "original"}]
        json.dump(test_data, test_file)
        test_file.close()
        
        # Temporarily override the DATA_FILE setting
        original_data_file = app.DATA_FILE
        app.DATA_FILE = Path(test_file.name)
        
        app.DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        
        dm = DataManager()
        await dm.initialize()
        
        # Get current version
        initial_version = dm.data_version
        
        # Try to replace with wrong version
        new_data = [{"id": 1, "value": "updated"}]
        result = await dm.replace_all_data(
            new_data,
            username="test",
            expected_version="wrong_version_12345"
        )
        
        # Should detect conflict
        assert result["status"] == "conflict", f"Expected conflict, got {result['status']}"
        assert result["current_version"] == initial_version, "Version mismatch"
        
        # Verify data wasn't changed
        data_info = await dm.get_data()
        assert data_info["data"][0]["value"] == "original", "Data was modified despite conflict"
        
        # Try with correct version
        result = await dm.replace_all_data(
            new_data,
            username="test",
            expected_version=initial_version
        )
        
        assert result["status"] == "success", f"Expected success, got {result['status']}"
        
        # Verify data was changed
        data_info = await dm.get_data()
        assert data_info["data"][0]["value"] == "updated", "Data wasn't updated"
        
        print("   ✅ Atomic version conflict detection works correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original DATA_FILE
        if original_data_file:
            app.DATA_FILE = original_data_file
        
        # Clean up test file
        if test_file and os.path.exists(test_file.name):
            os.unlink(test_file.name)
            # Also clean up lock file
            lock_file = test_file.name + '.lock'
            if os.path.exists(lock_file):
                os.unlink(lock_file)


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running Concurrency & Data Loss Fix Tests")
    print("="*60 + "\n")
    
    results = []
    
    # Test 1: Atomic writes
    results.append(await test_atomic_writes())
    print()
    
    # Test 2: DataManager locking
    results.append(await test_data_manager_locking())
    print()
    
    # Test 3: Version conflict detection
    results.append(await test_version_conflict_detection())
    print()
    
    # Summary
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        print("="*60)
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
