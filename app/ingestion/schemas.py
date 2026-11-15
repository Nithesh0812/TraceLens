from datetime import datetime
from typing import Literal
from pydantic import BaseModel,Field,AwareDatetime

class LogEvent(BaseModel):
    timestamp: AwareDatetime
    service:str = Field(min_length=1)
    level:Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]
    event:str = Field(min_length=1)

    request_id:str | None = None
    method:str | None = None
    path:str | None = None
    status_code:int | None = Field(default=None, ge=100, le=599)
    duration_ms:float | None = Field(default=None, ge=0)
    error:str | None = None