import json
import time
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.redaction import redact_sensitive


class ApiClient:
    def __init__(
        self,
        timeout_seconds: int,
        retries: int,
        retry_backoff_factor: float,
        retry_status_codes: list[int],
        request_logger,
        response_logger,
        error_logger,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_codes = retry_status_codes
        self.request_logger = request_logger
        self.response_logger = response_logger
        self.error_logger = error_logger

        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        # Keep urllib3 retries limited to safe methods. Retrying POST can create
        # duplicate financial transactions if the server processed the request.
        retry_strategy = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            status=self.retries,
            backoff_factor=self.retry_backoff_factor,
            status_forcelist=self.retry_status_codes,
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _reset_session(self) -> None:
        self.session.close()
        self.session = self._build_session()

    def _should_retry_request_error(self, method: str, attempt: int) -> bool:
        safe_methods = {"GET", "HEAD", "OPTIONS"}
        return method.upper() in safe_methods and attempt < self.retries

    def _sleep_before_retry(self, attempt: int) -> None:
        if self.retry_backoff_factor <= 0:
            return
        time.sleep(self.retry_backoff_factor * (2 ** max(attempt - 1, 0)))

    def _request_once(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        verify_ssl: bool = True,
    ) -> requests.Response:
        content_type = str((headers or {}).get("Content-Type", "")).lower()
        if "application/x-www-form-urlencoded" in content_type:
            return self.session.request(
                method=method,
                url=url,
                data=payload,
                headers=headers,
                timeout=self.timeout_seconds,
                verify=verify_ssl,
            )
        return self.session.request(
            method=method,
            url=url,
            json=payload,
            headers=headers,
            timeout=self.timeout_seconds,
            verify=verify_ssl,
        )

    def call(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
    ) -> Dict[str, Any]:
        request_started = time.perf_counter()
        self.request_logger.info(
            "REQUEST | %s | %s | headers=%s | payload=%s",
            method,
            url,
            json.dumps(redact_sensitive(headers or {}), ensure_ascii=False),
            json.dumps(redact_sensitive(payload or {}), ensure_ascii=False),
        )

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._request_once(method, url, payload, headers, verify_ssl)
                break
            except requests.RequestException as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                self._reset_session()
                if self._should_retry_request_error(method, attempt):
                    self.error_logger.warning(
                        "HTTP_RETRY | %s | attempt=%s | elapsed_ms=%s",
                        str(exc),
                        attempt,
                        elapsed_ms,
                    )
                    self._sleep_before_retry(attempt)
                    continue
                self.error_logger.exception("HTTP_ERROR | %s | elapsed_ms=%s", str(exc), elapsed_ms)
                return {
                    "status_code": None,
                    "body": {"error": str(exc), "error_type": exc.__class__.__name__},
                    "text": str(exc),
                    "elapsed_ms": elapsed_ms,
                    "headers": {},
                }

        try:
            elapsed_ms = int((time.perf_counter() - request_started) * 1000)
            parsed_body = self._safe_json(response)

            self.response_logger.info(
                "RESPONSE | %s | status=%s | elapsed_ms=%s | body=%s",
                url,
                response.status_code,
                elapsed_ms,
                json.dumps(redact_sensitive(parsed_body), ensure_ascii=False),
            )

            return {
                "status_code": response.status_code,
                "body": parsed_body,
                "text": response.text,
                "elapsed_ms": elapsed_ms,
                "headers": dict(response.headers),
            }
        except requests.RequestException as exc:
            elapsed_ms = int((time.perf_counter() - request_started) * 1000)
            self._reset_session()
            self.error_logger.exception("HTTP_ERROR | %s | elapsed_ms=%s", str(exc), elapsed_ms)
            return {
                "status_code": None,
                "body": {"error": str(exc), "error_type": exc.__class__.__name__},
                "text": str(exc),
                "elapsed_ms": elapsed_ms,
                "headers": {},
            }

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}
