import httpx
from datetime import datetime

def query_prometheus(query: str, base_url: str = "http://localhost:9090",) -> dict:
    url =f"{base_url.rstrip('/')}/api/v1/query"
    response =httpx.get(url,params={"query":query},timeout=10.0,)
    response.raise_for_status()
    payload=response.json()
    if payload.get("status") != "success":
        raise ValueError(f"Prometheus query failed: {payload.get('error', 'Unknown error')}")
    return payload["data"]

def query_prometheus_range(query: str,start: datetime,end: datetime,step: str = "15s",base_url: str = "http://localhost:9090",) -> dict:
    if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
        raise ValueError("start and End must be timezone-aware")

    if start > end:
        raise ValueError("start cannot be after end time")
    
    url=f"{base_url.rstrip('/')}/api/v1/query_range"

    params ={
        "query":query,
        "start":start.timestamp(),
        "end":end.timestamp(),
        "step":step,
    }
    response = httpx.get(url,params=params,timeout=10.0,)
    response.raise_for_status()
    payload=response.json()
    if payload.get("status") != "success":
        raise ValueError(
        f"Prometheus range query failed: "
        f"{payload.get('error', 'Unknown error')}")
    return payload["data"]