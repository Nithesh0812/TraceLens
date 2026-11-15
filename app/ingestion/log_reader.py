import json
from pathlib import Path
from pydantic import ValidationError
from app.ingestion.schemas import LogEvent

def read_logs(file_path:str) -> list[LogEvent]:
    logs=[]

    path = Path(file_path)

    with path.open("r",encoding= "utf-8") as file:
        for line_number,line in enumerate(file,start=1):
            if not line.strip():
                continue
            try:
                event = LogEvent.model_validate(json.loads(line))
                logs.append(event)
            except(json.JSONDecodeError,ValidationError) as exc:
                print(f"Invalid log at line {line_number}: {exc}")
            
    return logs
