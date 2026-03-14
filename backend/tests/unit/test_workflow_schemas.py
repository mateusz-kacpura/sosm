import pytest
from pydantic import ValidationError
from datetime import datetime

from app.models.workflow_schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListItem,
    WorkflowRunCreate,
    WorkflowRunResponse,
    NodeExecutionResponse,
)


class TestWorkflowCreate:
    def test_valid_minimal(self):
        wf = WorkflowCreate(name="Test")
        assert wf.name == "Test"
        assert wf.description is None
        assert wf.account_id is None
        assert wf.graph_data is None

    def test_valid_full(self):
        wf = WorkflowCreate(
            name="Full",
            description="A full workflow",
            account_id=1,
            graph_data={"nodes": [], "edges": []},
        )
        assert wf.description == "A full workflow"
        assert wf.account_id == 1
        assert wf.graph_data == {"nodes": [], "edges": []}

    def test_missing_name(self):
        with pytest.raises(ValidationError):
            WorkflowCreate(description="No name")


class TestWorkflowUpdate:
    def test_all_none(self):
        update = WorkflowUpdate()
        assert update.name is None
        assert update.status is None
        assert update.graph_data is None
        assert update.schedule_type is None
        assert update.schedule_config is None

    def test_partial_update(self):
        update = WorkflowUpdate(name="New Name", status="AKTYWNY")
        assert update.name == "New Name"
        assert update.status == "AKTYWNY"
        assert update.description is None

    def test_schedule_config(self):
        update = WorkflowUpdate(
            schedule_type="interval",
            schedule_config={"interval_minutes": 30},
        )
        assert update.schedule_type == "interval"
        assert update.schedule_config["interval_minutes"] == 30


class TestWorkflowResponse:
    def test_from_attributes(self):
        class FakeWorkflow:
            id = 1
            name = "Test"
            description = None
            account_id = None
            graph_data = {"nodes": [], "edges": []}
            status = "SZKIC"
            schedule_type = None
            schedule_config = None
            created_at = datetime(2026, 1, 1)
            updated_at = datetime(2026, 1, 1)

        resp = WorkflowResponse.model_validate(FakeWorkflow(), from_attributes=True)
        assert resp.id == 1
        assert resp.name == "Test"
        assert resp.status == "SZKIC"


class TestWorkflowListItem:
    def test_from_attributes(self):
        class FakeItem:
            id = 1
            name = "Listed"
            description = "A listed workflow"
            account_id = 5
            status = "AKTYWNY"
            node_count = 10
            last_run_status = "COMPLETED"
            created_at = datetime(2026, 3, 1)

        item = WorkflowListItem.model_validate(FakeItem(), from_attributes=True)
        assert item.node_count == 10
        assert item.last_run_status == "COMPLETED"

    def test_defaults(self):
        class FakeItem:
            id = 1
            name = "Minimal"
            description = None
            account_id = None
            status = "SZKIC"
            node_count = 0
            last_run_status = None
            created_at = datetime(2026, 1, 1)

        item = WorkflowListItem.model_validate(FakeItem(), from_attributes=True)
        assert item.node_count == 0
        assert item.last_run_status is None


class TestWorkflowRunCreate:
    def test_empty(self):
        run = WorkflowRunCreate()
        assert run.variables is None

    def test_with_variables(self):
        run = WorkflowRunCreate(variables={"key": "value"})
        assert run.variables == {"key": "value"}


class TestWorkflowRunResponse:
    def test_from_attributes(self):
        class FakeRun:
            id = 1
            workflow_id = 10
            status = "RUNNING"
            trigger_type = "manual"
            variables = {"x": 1}
            started_at = datetime(2026, 3, 1, 10, 0)
            completed_at = None
            error_message = None
            created_at = datetime(2026, 3, 1, 10, 0)

        resp = WorkflowRunResponse.model_validate(FakeRun(), from_attributes=True)
        assert resp.id == 1
        assert resp.status == "RUNNING"
        assert resp.trigger_type == "manual"

    def test_failed_run(self):
        class FakeRun:
            id = 2
            workflow_id = 10
            status = "FAILED"
            trigger_type = "scheduled"
            variables = None
            started_at = datetime(2026, 3, 1, 10, 0)
            completed_at = datetime(2026, 3, 1, 10, 5)
            error_message = "Browser crash"
            created_at = datetime(2026, 3, 1, 10, 0)

        resp = WorkflowRunResponse.model_validate(FakeRun(), from_attributes=True)
        assert resp.error_message == "Browser crash"
        assert resp.completed_at is not None


class TestNodeExecutionResponse:
    def test_from_attributes(self):
        class FakeExec:
            id = 1
            run_id = 10
            node_id = "node_1"
            node_type = "post_group"
            status = "COMPLETED"
            input_data = {"group_url": "https://fb.com/groups/1"}
            output_data = {"success": True}
            error_message = None
            screenshot_path = None
            started_at = datetime(2026, 3, 1, 10, 0)
            completed_at = datetime(2026, 3, 1, 10, 1)

        resp = NodeExecutionResponse.model_validate(FakeExec(), from_attributes=True)
        assert resp.node_type == "post_group"
        assert resp.output_data == {"success": True}

    def test_failed_execution(self):
        class FakeExec:
            id = 2
            run_id = 10
            node_id = "node_2"
            node_type = "login"
            status = "FAILED"
            input_data = {}
            output_data = None
            error_message = "Connection refused"
            screenshot_path = "/screenshots/err.png"
            started_at = datetime(2026, 3, 1, 10, 0)
            completed_at = datetime(2026, 3, 1, 10, 0)

        resp = NodeExecutionResponse.model_validate(FakeExec(), from_attributes=True)
        assert resp.error_message == "Connection refused"
        assert resp.screenshot_path == "/screenshots/err.png"
