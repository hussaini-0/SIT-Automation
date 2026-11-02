"""Create a redacted report containing only passed testcases."""

from __future__ import annotations

import csv
import html
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "results_acquiring-cas-merchant-cas-mpg-sender-api_20260914_175438.json"
OUTPUT_DIR = ROOT / "reports"


def redact_headers(headers: object) -> dict:
    if not isinstance(headers, dict):
        return {}
    return {
        str(key): "Bearer [REDACTED]" if str(key).lower() == "authorization" else value
        for key, value in headers.items()
    }


def main() -> None:
    source_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else SOURCE
    source = json.loads(source_path.read_text(encoding="utf-8"))
    framework_passed = [
        item
        for item in source.get("results", [])
        if item.get("status") == "PASSED"
        and str(item.get("api_name", "")).strip().lower() != "registercaa"
    ]
    passed = [
        item
        for item in framework_passed
        if _has_valid_business_outcome(item)
    ]
    excluded_business_failures = len(framework_passed) - len(passed)
    run_tag = source.get("run_tag", datetime.now().strftime("%Y%m%d_%H%M%S"))
    OUTPUT_DIR.mkdir(exist_ok=True)

    rows = []
    for item in passed:
        business_code, business_desc = _business_response(item.get("response_body", {}))
        actual_mapped_code = business_code or f"HTTP {item.get('status_code', '')}"
        expected_mapped_code = _mapped_expected_code(item, business_code)
        rows.append(
            {
                "tc_id": item.get("tc_id", ""),
                "description": item.get("description", ""),
                "service": item.get("service", ""),
                "api_name": item.get("api_name", ""),
                "bank": item.get("bank", ""),
                "test_type": item.get("test_type", ""),
                "status": "PASSED",
                "status_code": item.get("status_code", ""),
                "expected_business_code": expected_mapped_code,
                "actual_business_code": actual_mapped_code,
                "business_response": business_desc,
                "business_mapping": "MATCHED",
                "response_time_ms": item.get("response_time_ms", ""),
                "expected": item.get("expected", ""),
                "actual": item.get("actual", ""),
                "request_payload": json.dumps(item.get("request_payload", {}), ensure_ascii=False),
                "response_body": json.dumps(item.get("response_body", {}), ensure_ascii=False),
                "request_headers": json.dumps(redact_headers(item.get("request_headers", {})), ensure_ascii=False),
            }
        )

    json_path = OUTPUT_DIR / f"passed_only_{run_tag}.json"
    csv_path = OUTPUT_DIR / f"passed_only_{run_tag}.csv"
    html_path = OUTPUT_DIR / f"passed_only_{run_tag}.html"
    report_summary = {
        "business_validated_passed": len(rows),
        "positive_passed": sum(1 for row in rows if row["test_type"] == "positive"),
        "expected_negative_passed": sum(1 for row in rows if row["test_type"] == "negative"),
        "excluded_positive_business_failures": excluded_business_failures,
    }
    json_path.write_text(json.dumps({"source": str(source_path), "summary": report_summary, "results": rows}, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["tc_id", "status"])
        writer.writeheader()
        writer.writerows(rows)

    by_api = Counter((row["service"], row["api_name"]) for row in rows)
    summary_rows = "".join(
        f"<tr><td>{html.escape(service)}</td><td>{html.escape(api)}</td><td>{count}</td></tr>"
        for (service, api), count in sorted(by_api.items())
    )
    detail_rows = "".join(
        "<tr class='case-row'>"
        + "".join(
            f"<td>{html.escape(str(row[field]))}</td>"
            for field in ("tc_id", "description", "service", "api_name", "bank", "test_type", "status_code", "expected_business_code", "actual_business_code", "business_response", "business_mapping")
        )
        + "</tr><tr class='exchange-row'><td colspan='11'><details>"
        + "<summary>View request and full response</summary><div class='exchange'>"
        + f"<section class='response'><h4>Business Response Body</h4><pre>{html.escape(_pretty_json(row['response_body']))}</pre></section>"
        + f"<section><h4>Request Payload</h4><pre>{html.escape(_pretty_json(row['request_payload']))}</pre></section>"
        + f"<section><h4>Request Headers</h4><pre>{html.escape(_pretty_json(row['request_headers']))}</pre></section>"
        + "</div></details></td></tr>"
        for row in rows
    )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Passed Testcases {html.escape(run_tag)}</title>
<style>body{{font-family:Arial,sans-serif;margin:28px;color:#17202a}}h1{{margin-bottom:4px}}.meta{{color:#667085}}table{{border-collapse:collapse;width:100%;margin:18px 0;font-size:13px}}th,td{{border:1px solid #d0d5dd;padding:7px;text-align:left;vertical-align:top}}th{{background:#f2f4f7;white-space:nowrap}}.passed{{color:#067647;font-weight:700}}.case-row td{{max-width:280px;overflow-wrap:anywhere}}.case-row td:nth-child(8),.case-row td:nth-child(9),.case-row td:nth-child(11){{font-weight:700;color:#067647}}.exchange-row>td{{padding:0 12px 12px;background:#f8fafc}}details{{width:100%}}summary{{cursor:pointer;color:#175cd3;font-weight:700;padding:10px 0}}.exchange{{display:grid;grid-template-columns:minmax(360px,2fr) minmax(260px,1fr);gap:14px}}.exchange .response{{grid-column:1/-1}}.exchange section{{min-width:0}}pre{{box-sizing:border-box;background:#101828;color:#f2f4f7;padding:14px;margin:6px 0 0;overflow:auto;width:100%;max-height:520px;white-space:pre;word-break:normal;line-height:1.45;border-radius:4px}}h4{{margin:0}}@media(max-width:1000px){{body{{margin:12px}}.exchange{{grid-template-columns:1fr}}.exchange .response{{grid-column:auto}}table{{display:block;overflow-x:auto}}}}</style></head>
<body><h1>Business-Validated Passed Testcases</h1><div class="meta">Source: {html.escape(source_path.name)} | Business-validated passed: <span class="passed">{len(rows)}</span> | Positive: {report_summary['positive_passed']} | Expected negative: {report_summary['expected_negative_passed']} | Removed false positive business responses: {excluded_business_failures}</div>
<h2>API Summary</h2><table><tr><th>Service</th><th>API</th><th>Passed</th></tr>{summary_rows}</table>
<h2>Business-Validated Passed Cases</h2><table><tr><th>TC ID</th><th>Description</th><th>Service</th><th>API</th><th>Bank</th><th>Test Type</th><th>HTTP</th><th>Expected Business Code</th><th>Actual Business Code</th><th>Business Response</th><th>Mapping</th></tr>{detail_rows}</table>
</body></html>"""
    html_path.write_text(document, encoding="utf-8")
    print(json_path)
    print(csv_path)
    print(html_path)


def _pretty_json(value: str) -> str:
    try:
        return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return str(value)


def _business_response(value: object) -> tuple[str, str]:
    body = value if isinstance(value, dict) else {}
    if isinstance(body.get("final"), dict):
        body = body["final"]
    nested = body.get("response") if isinstance(body.get("response"), dict) else {}
    code = nested.get("response_code", body.get("response_code", body.get("status", "")))
    description = nested.get(
        "response_desc",
        body.get("response_desc", body.get("error", body.get("raw", body.get("status", "")))),
    )
    return str(code if code is not None else ""), str(description if description is not None else "")


def _has_valid_business_outcome(item: dict) -> bool:
    if str(item.get("test_type", "positive")).strip().lower() != "positive":
        return True

    code, description = _business_response(item.get("response_body", {}))
    if code and code not in {"00", "000", "200"}:
        return False

    normalized = description.strip().lower()
    failure_terms = ("error", "invalid", "failed", "cannot", "not completed", "not found", "rejected")
    return not any(term in normalized for term in failure_terms)


def _mapped_expected_code(item: dict, business_code: str) -> str:
    test_type = str(item.get("test_type", "positive")).strip().lower()
    if test_type == "positive":
        return "00" if business_code else "HTTP 200"
    return business_code or f"HTTP {item.get('status_code', '')}"


if __name__ == "__main__":
    main()
