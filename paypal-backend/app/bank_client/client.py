import json
import asyncio
from typing import Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

from app.config import settings
from app.logging_config import request_id_var
from app.bank_client.hmac_signer import build_bank_headers

logger = structlog.get_logger()


class BankUnavailableError(Exception):
    pass


class AsyncCircuitBreaker:
    """
    Simple async-compatible circuit breaker.
    States: CLOSED (normal), OPEN (blocking), HALF_OPEN (testing).
    
    This replaces pybreaker.call_async which has a tornado dependency bug.
    """

    def __init__(self, fail_max: int = 5, reset_timeout: float = 30.0, name: str = "breaker"):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.name = name
        self._failures = 0
        self._state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def call(self, coro_func, *args, **kwargs):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            if self._state == "OPEN":
                if now - self._opened_at >= self.reset_timeout:
                    self._state = "HALF_OPEN"
                    logger.info("circuit_breaker_half_open", breaker=self.name)
                else:
                    raise BankUnavailableError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await coro_func(*args, **kwargs)
            async with self._lock:
                if self._state == "HALF_OPEN":
                    self._state = "CLOSED"
                    self._failures = 0
                    logger.info("circuit_breaker_closed", breaker=self.name)
            return result
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            async with self._lock:
                self._failures += 1
                if self._failures >= self.fail_max:
                    self._state = "OPEN"
                    self._opened_at = asyncio.get_event_loop().time()
                    logger.error("circuit_breaker_opened", breaker=self.name, failures=self._failures)
            raise


# One breaker per bank (module-level singletons)
bank_x_breaker = AsyncCircuitBreaker(fail_max=5, reset_timeout=30, name="bank_x_breaker")
bank_y_breaker = AsyncCircuitBreaker(fail_max=5, reset_timeout=30, name="bank_y_breaker")


class BankClient:
    def __init__(self, bank_id: str):
        self.bank_id = bank_id
        if bank_id == "bank_x":
            self.base_url = settings.BANK_X_API_URL
            self.api_key = settings.BANK_X_API_KEY
            self.breaker = bank_x_breaker
        elif bank_id == "bank_y":
            self.base_url = settings.BANK_Y_API_URL
            self.api_key = settings.BANK_Y_API_KEY
            self.breaker = bank_y_breaker
        else:
            raise ValueError(f"Unknown bank_id: {bank_id}")

        self.hmac_secret = settings.BANK_HMAC_SECRET

    async def _execute_http(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        body_str = json.dumps(body) if body is not None else ""
        req_id = request_id_var.get()
        headers = build_bank_headers(
            method=method,
            path=path,
            body_str=body_str,
            api_key=self.api_key,
            hmac_secret=self.hmac_secret,
            request_id=req_id,
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{path}",
                content=body_str if body is not None else None,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def _call(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            return await self.breaker.call(self._execute_http, method, path, body)
        except BankUnavailableError:
            logger.error("bank_circuit_breaker_open", bank_id=self.bank_id)
            raise
        except httpx.HTTPStatusError as e:
            logger.warning("bank_http_error", bank_id=self.bank_id, status_code=e.response.status_code)
            try:
                return e.response.json()
            except Exception:
                raise e
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning("bank_network_error", bank_id=self.bank_id, error=str(e))
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def debit(self, reference_id: str, token: str, amount: int) -> Dict[str, Any]:
        """Safe to retry with exponential backoff because debit is idempotent on reference_id."""
        return await self._call(
            "POST",
            "/api/debit",
            {"reference_id": reference_id, "token": token, "amount": amount},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def credit(self, reference_id: str, token: str, amount: int) -> Dict[str, Any]:
        """Safe to retry with exponential backoff because credit is idempotent on reference_id."""
        return await self._call(
            "POST",
            "/api/credit",
            {"reference_id": reference_id, "token": token, "amount": amount},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def get_status(self, reference_id: str) -> Dict[str, Any]:
        return await self._call("GET", f"/api/status/{reference_id}")

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        return await self._call("POST", "/api/exchange-code", {"code": code})

    async def request_link(
        self,
        request_id: str,
        account_no: str,
        requester_name: str = "MiniPay",
        purpose: str = "Link bank account for payments",
        per_txn_limit: int = 5000000,
    ) -> Dict[str, Any]:
        return await self._call(
            "POST",
            "/api/link-request",
            {
                "request_id": request_id,
                "account_no": account_no,
                "requester_name": requester_name,
                "purpose": purpose,
                "per_txn_limit": per_txn_limit,
            },
        )

