import uuid
from locust import HttpUser, task, between, events
import structlog

logger = structlog.get_logger()


class MiniPayUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self):
        self.email = f"loadtest_{uuid.uuid4().hex[:8]}@example.com"
        self.password = "Password123!"

        # Register
        reg_res = self.client.post("/api/auth/register", json={
            "email": self.email,
            "password": self.password,
        })
        if reg_res.status_code == 201:
            # Login
            login_res = self.client.post("/api/auth/login", json={
                "email": self.email,
                "password": self.password,
            })
            if login_res.status_code == 200:
                self.token = login_res.json()["access_token"]
                self.auth_headers = {"Authorization": f"Bearer {self.token}"}
            else:
                self.token = None
        else:
            self.token = None

    @task(10)
    def check_balance(self):
        if not self.token:
            return
        self.client.get("/api/wallet/balance", headers=self.auth_headers)

    @task(5)
    def transfer_money(self):
        if not self.token:
            return
        idempotency_key = str(uuid.uuid4())
        headers = {
            **self.auth_headers,
            "Idempotency-Key": idempotency_key,
        }
        # Send to admin user
        self.client.post("/api/payments/send", json={
            "recipient_email": "admin@minipay.com",
            "amount": 500,  # 5 INR
            "source": "WALLET",
        }, headers=headers)

    @task(2)
    def view_transactions(self):
        if not self.token:
            return
        self.client.get("/api/payments?per_page=10", headers=self.auth_headers)
