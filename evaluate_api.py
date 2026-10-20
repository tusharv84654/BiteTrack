import time
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
NUM_REQUESTS = 20

def evaluate_menu_endpoint():
    latencies = []
    print(f"\n--- 1. Evaluating GET /api/menu/ ({NUM_REQUESTS} iterations) ---")
    
    for i in range(NUM_REQUESTS):
        start = time.perf_counter()
        try:
            with urlopen(f"{BASE_URL}/api/menu/") as res:
                status_code = res.status
                payload = json.loads(res.read().decode("utf-8"))
        except HTTPError as res:
            status_code = res.code
            payload = None
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        if status_code == 200:
            latencies.append(elapsed)
            payload_items = payload
        else:
            print(f"Request {i+1} failed with status {status_code}")

    if not latencies:
        print("No successful requests; unable to calculate response times.")
        return
    avg_latency = sum(latencies) / len(latencies)
    print(f"Status Code: 200 OK")
    print(f"Payload Items Count: {len(payload_items)}")
    print(f"Average Response Time: {avg_latency:.2f} ms")
    print(f"Fastest Response Time: {min(latencies):.2f} ms")
    print(f"Slowest Response Time: {max(latencies):.2f} ms")

def get_auth_token():
    data = json.dumps({
        "username": "admin",
        "password": "your_admin_password"  # <-- put your admin password here
    }).encode("utf-8")
    request = Request(
        f"{BASE_URL}/api/auth/token/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request) as res:
            if res.status == 200:
                return json.loads(res.read().decode("utf-8")).get("token")
    except HTTPError:
        pass
    return None

if __name__ == "__main__":
    evaluate_menu_endpoint()