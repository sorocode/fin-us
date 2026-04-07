import requests
import time

def test_api(stock):
    url = f"http://localhost:8000/api/v1/news?stock={stock}"
    print(f"Testing Python Backend for: {stock}")
    start = time.time()
    try:
        response = requests.get(url, timeout=60)
        end = time.time()
        print(f"Status: {response.status_code}")
        print(f"Time: {end - start:.2f}s")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

    url_express = f"http://localhost:3000/api/v1/news?stock={stock}"
    print(f"\nTesting Express Backend for: {stock}")
    start = time.time()
    try:
        response = requests.get(url_express, timeout=60)
        end = time.time()
        print(f"Status: {response.status_code}")
        print(f"Time: {end - start:.2f}s")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api("삼성전자")
