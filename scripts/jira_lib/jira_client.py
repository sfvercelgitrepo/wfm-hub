import time
from typing import Any, Dict, List, Optional, Union

import requests

# Use with search_issues(fields=ALL_JIRA_FIELDS) to request every field Jira returns.
ALL_JIRA_FIELDS: List[str] = ["*all"]

# POST /rest/api/3/search/jql returns id-only stubs if `fields` is omitted.
# These cover `normalize_issue` in transform.py (incl. common Cloud custom fields).
DEFAULT_JIRA_SEARCH_FIELDS: List[str] = [
    "summary",
    "project",
    "issuetype",
    "status",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "duedate",
    "labels",
    "parent",
    "customfield_10016",
    "customfield_10026",
    "customfield_10020",
    "customfield_10010",
    "customfield_10014",
    "customfield_10008",
]


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        timeout_seconds: int = 30,
        max_retries: int = 4,
        backoff_seconds: float = 1.5,
        ssl_verify: Union[bool, str] = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        self.session.verify = ssl_verify

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Jira request failed: {exc}") from exc
                sleep_for = self.backoff_seconds * (2**attempt)
                time.sleep(sleep_for)
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after else self.backoff_seconds * (2**attempt)
                time.sleep(sleep_for)
                continue

            response.raise_for_status()
            return response

        raise RuntimeError(f"Unable to complete Jira request: {last_error}")

    def search_issues(
        self,
        jql: str,
        max_results: Optional[int] = None,
        page_size: int = 100,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        requested_total = max_results if max_results is not None else float("inf")

        try:
            return self._search_enhanced_post(
                jql, max_results, page_size, fields, issues, requested_total
            )
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {400, 404, 410}:
                return self._search_legacy(
                    jql, max_results, page_size, fields, issues, requested_total
                )
            raise

    def _search_enhanced_post(
        self,
        jql: str,
        max_results: Optional[int],
        page_size: int,
        fields: Optional[List[str]],
        issues: List[Dict[str, Any]],
        requested_total: float,
    ) -> List[Dict[str, Any]]:
        """Jira Cloud enhanced JQL: POST /rest/api/3/search/jql (token pagination)."""
        next_page_token: Optional[str] = None
        while len(issues) < requested_total:
            chunk_size = (
                min(page_size, int(requested_total - len(issues)))
                if max_results is not None
                else page_size
            )
            body: Dict[str, Any] = {
                "jql": jql,
                "maxResults": chunk_size,
                "fields": fields if fields is not None else DEFAULT_JIRA_SEARCH_FIELDS,
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token

            response = self._request_with_retry(
                "POST",
                "/rest/api/3/search/jql",
                json=body,
            )
            payload = response.json()
            page_issues = payload.get("issues", [])
            if not page_issues:
                break
            issues.extend(page_issues)
            if max_results is not None and len(issues) >= max_results:
                return issues[:max_results]

            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break

        if max_results is not None:
            return issues[:max_results]
        return issues

    def _search_legacy(
        self,
        jql: str,
        max_results: Optional[int],
        page_size: int,
        fields: Optional[List[str]],
        issues: List[Dict[str, Any]],
        requested_total: float,
    ) -> List[Dict[str, Any]]:
        """
        Legacy offset pagination: try GET /rest/api/3/search, then GET /search/jql.
        Some tenants still return 200 here; others return 410 (caller may need migration only).
        """
        issues.clear()
        start_at = 0
        endpoints = ["/rest/api/3/search", "/rest/api/3/search/jql"]
        last_error: Optional[Exception] = None
        for endpoint in endpoints:
            try:
                issues.clear()
                start_at = 0
                while len(issues) < requested_total:
                    chunk_size = (
                        min(page_size, int(requested_total - len(issues)))
                        if max_results is not None
                        else page_size
                    )
                    params: Dict[str, Any] = {
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": chunk_size,
                    }
                    if fields:
                        if fields == ALL_JIRA_FIELDS:
                            params["fields"] = "*all"
                        else:
                            params["fields"] = ",".join(fields)
                    response = self._request_with_retry("GET", endpoint, params=params)
                    payload = response.json()
                    page_issues = payload.get("issues", [])
                    if not page_issues:
                        break
                    issues.extend(page_issues)
                    total = payload.get("total", 0) or 0
                    start_at += len(page_issues)
                    if start_at >= total:
                        break
                if max_results is not None:
                    return issues[:max_results]
                return issues
            except requests.HTTPError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return issues if max_results is None else issues[: max_results or 0]

    def list_fields(self) -> List[Dict[str, Any]]:
        """Return field metadata (id, name, custom, ...) from Jira."""
        response = self._request_with_retry("GET", "/rest/api/3/field")
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return payload.get("values", [])
