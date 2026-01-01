
import requests
import json

BASE_URL = "http://localhost:8000"

def test_auth():
    print("Testing Authentication Flow...")
    
    # 1. Login
    login_url = f"{BASE_URL}/api/auth/login"
    payload = {
        "username": "admin",
        "password": "admin123"
    }
    
    session = requests.Session()
    response = session.post(login_url, json=payload)
    
    print(f"Login Status: {response.status_code}")
    print(f"Login Response: {response.json()}")
    print(f"Cookies after login: {session.cookies.get_dict()}")
    
    if response.status_code != 200:
        print("Login failed!")
        return

    # 2. Access Dashboard
    dashboard_url = f"{BASE_URL}/dashboard"
    response = session.get(dashboard_url)
    
    print(f"Dashboard Status: {response.status_code}")
    if response.status_code == 200:
        print("Dashboard access SUCCESSFUL!")
    else:
        print(f"Dashboard access FAILED with {response.status_code}")
        # Try to see if there's any JSON detail
        try:
            print(f"Error Detail: {response.json()}")
        except:
            print("Response is not JSON (likely HTML redirect or error page)")

if __name__ == "__main__":
    try:
        test_auth()
    except Exception as e:
        print(f"An error occurred: {e}")
