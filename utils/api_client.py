import json
import time
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
        self.request_logger = request_logger
        self.response_logger = response_logger
        self.error_logger = error_logger

        self.session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=retry_backoff_factor,
            status_forcelist=retry_status_codes,
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def call(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        request_started = time.perf_counter()
        self.request_logger.info(
            "REQUEST | %s | %s | headers=%s | payload=%s",
            method,
            url,
            json.dumps(headers or {}, ensure_ascii=False),
            json.dumps(payload or {}, ensure_ascii=False),
        )

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            elapsed_ms = int((time.perf_counter() - request_started) * 1000)
            parsed_body = self._safe_json(response)

            self.response_logger.info(
                "RESPONSE | %s | status=%s | elapsed_ms=%s | body=%s",
                url,
                response.status_code,
                elapsed_ms,
                json.dumps(parsed_body, ensure_ascii=False),
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
            self.error_logger.exception("HTTP_ERROR | %s | elapsed_ms=%s", str(exc), elapsed_ms)
            return {
                "status_code": None,
                "body": {"error": str(exc)},
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
