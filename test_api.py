import requests
import json

BASE_URL = "http://localhost:5000"

def test_home():
    """Test home endpoint"""
    response = requests.get(f"{BASE_URL}/")
    print("🏠 Home endpoint:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print("❤️ Health endpoint:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_webhook(user_id, message):
    """Test webhook endpoint"""
    payload = {
        "message": {"text": message},
        "user": {"id": user_id}
    }
    
    response = requests.post(
        f"{BASE_URL}/webhook",
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    print(f"🤖 Webhook test - User: {user_id}, Message: '{message}'")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_full_dialog():
    """Test complete dialog flow"""
    user_id = "test_user_123"
    
    print("🎭 Testing full dialog flow:")
    print("=" * 50)
    
    # Step 1: Year
    test_webhook(user_id, "2020")
    
    # Step 2: Habit
    test_webhook(user_id, "кофе")
    
    # Step 3: Daily cost
    test_webhook(user_id, "500")
    
    # Step 4: Currency
    test_webhook(user_id, "рубли")
    
    # Step 5: Confirmation
    test_webhook(user_id, "да")

if __name__ == "__main__":
    print("🧪 Testing Financial Assistant API")
    print("=" * 50)
    
    # Test basic endpoints
    test_home()
    test_health()
    
    # Test individual webhook calls
    print("📝 Testing individual webhook calls:")
    test_webhook("user1", "2020")
    test_webhook("user1", "кофе")
    test_webhook("user1", "500")
    test_webhook("user1", "рубли")
    test_webhook("user1", "да")
    
    print("🎭 Testing full dialog flow:")
    test_full_dialog() 