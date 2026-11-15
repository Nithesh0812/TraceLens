from app.ingestion.schemas import LogEvent
from datetime import datetime

def filter_logs(logs:list[LogEvent], level:str |None = None, event:str |None = None,request_id: str | None = None, start_time:datetime |None =None, end_time:datetime |None=None)-> list[LogEvent]:
    filtered_logs=[]

    for log in logs:
        if level is not None and log.level!= level:
            continue

        if event is not None and log.event!= event:
            continue

        if request_id is not None and log.request_id!= request_id:
            continue

        if start_time is not None and log.timestamp < start_time:
            continue
        if end_time is not None and log.timestamp > end_time:
                    continue
        filtered_logs.append(log)


    return filtered_logs