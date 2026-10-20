from locust import HttpUser, task, between
import json

class CanteenApiUser(HttpUser):
    # Wait between 1 and 2 seconds between consecutive tasks to simulate human pace
    wait_time = between(1, 2)

    # 1. READ Test: Simulates students browsing the menu
    @task(3)
    def view_menu(self):
        self.client.get("/api/menu/", name="GET /api/menu/")

    # 2. WRITE Test: Simulates students placing orders with JSON payload
    @task(1)
    def place_order(self):
        # Sample order JSON payload
        payload = {
            "items": [
                {"item_id": 1, "quantity": 1}
            ]
        }
        headers = {
            "Content-Type": "application/json",
            # Replace with a valid token generated from /admin/ or /api/auth/token/
            "Authorization": "Token YOUR_AUTH_TOKEN_HERE"
        }
        self.client.post(
            "/api/orders/place/",
            data=json.dumps(payload),
            headers=headers,
            name="POST /api/orders/place/"
        )