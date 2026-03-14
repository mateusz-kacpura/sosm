from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    # React Flow graph: { nodes: [...], edges: [...], viewport: {...} }
    graph_data = Column(
        JSON, nullable=False,
        default=lambda: {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )

    # SZKIC, AKTYWNY, WSTRZYMANY
    status = Column(String, default="SZKIC")

    # Optional schedule: "manual", "interval", "cron"
    schedule_type = Column(String, nullable=True)
    # e.g. {"interval_minutes": 60} or {"cron": "0 */6 * * *"}
    schedule_config = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account", backref="workflows")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)

    # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    status = Column(String, default="PENDING")
    trigger_type = Column(String, default="manual")  # manual, scheduled

    # Runtime variable context (accumulated during execution)
    variables = Column(JSON, nullable=True, default=dict)

    # Snapshot of graph_data at execution time (immutable record)
    graph_snapshot = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("Workflow", back_populates="runs")
    node_executions = relationship(
        "WorkflowNodeExecution", back_populates="run", cascade="all, delete-orphan",
    )


class WorkflowNodeExecution(Base):
    __tablename__ = "workflow_node_executions"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    node_id = Column(String, nullable=False)   # React Flow node ID (e.g. "node_1")
    node_type = Column(String, nullable=False)  # "login", "post_group", "wait", etc.

    # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    status = Column(String, default="PENDING")

    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    run = relationship("WorkflowRun", back_populates="node_executions")
