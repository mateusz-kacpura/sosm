from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


# ── Workflow ──

class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    account_id: Optional[int] = None
    graph_data: Optional[dict] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    account_id: Optional[int] = None
    graph_data: Optional[dict] = None
    status: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[dict] = None


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    account_id: Optional[int] = None
    graph_data: dict
    status: str
    schedule_type: Optional[str] = None
    schedule_config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowListItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    account_id: Optional[int] = None
    status: str
    node_count: int = 0
    last_run_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Run ──

class WorkflowRunCreate(BaseModel):
    variables: Optional[dict] = None


class WorkflowRunResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    trigger_type: str
    variables: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Node Execution ──

class NodeExecutionResponse(BaseModel):
    id: int
    run_id: int
    node_id: str
    node_type: str
    status: str
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
