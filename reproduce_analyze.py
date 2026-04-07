import requests
import time

def test_analyze(stock):
    url = f"http://localhost:8000/api/v1/analyze?stock={stock}&provider=openai"
    print(f"Testing Python Analyze for: {stock}")
    start = time.time()
    try:
        response = requests.get(url, timeout=60)
        end = time.time()
        print(f"Status: {response.status_code}")
        print(f"Time: {end - start:.2f}s")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_analyze("삼성전자")
