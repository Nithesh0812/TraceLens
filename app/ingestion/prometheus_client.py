import httpx


def query_prometheus(query: str, base_url: str = "http://localhost:9090",) -> dict:
    url =f"{base_url.rstrip("/")}/api/v1/query"
    response =httpx.get(url,params={"query":query},timeout=10.0,)
    response.raise_for_status()
    payload=response.json()
    if payload.get("status") != "success":
        raise ValueError(f"Prometheus query failed: {payload.get('error', 'Unknown error')}")
    return payload["data"]