#!/usr/bin/env python3
"""Test script to verify auto-save triggers after 3 modifications"""
import requests
import time

BASE_URL = "http://localhost:7860"

def test_autosave():
    print("🧪 Testing auto-save with 15 modifications...\n")
    
    # Get initial stats
    response = requests.get(f"{BASE_URL}/stats")
    initial_stats = response.json()
    print(f"Initial unsaved changes: {initial_stats['unsaved_changes']}")
    
    # Make 15 modifications
    for i in range(1, 16):
        print(f"\n📝 Making modification #{i}...")
        response = requests.post(
            f"{BASE_URL}/update",
            json={
                "index": 0,
                "updates": {"test_field": f"test_value_{i}_{time.time()}"}
            },
            headers={"X-Username": "test_user"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Update successful")
            
            # Check stats
            stats = requests.get(f"{BASE_URL}/stats").json()
            print(f"   Unsaved changes: {stats['unsaved_changes']}")
            
            # At multiples of 3, wait for save
            if i % 3 == 0:
                print(f"   ⏳ Waiting for auto-save (should trigger at 3 mods)...")
                time.sleep(12)  # Wait for auto-save to trigger
                stats = requests.get(f"{BASE_URL}/stats").json()
                if stats['unsaved_changes'] == 0:
                    print(f"   ✅ Save triggered! Unsaved count reset to 0")
                else:
                    print(f"   ❌ Save did NOT trigger! Still {stats['unsaved_changes']} unsaved")
        else:
            print(f"   ❌ Update failed: {response.status_code}")
            return
        
        # Wait a bit between modifications
        time.sleep(1)
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    try:
        test_autosave()
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()

