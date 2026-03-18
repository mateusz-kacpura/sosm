from datetime import datetime, timezone
from app.models.models import Account, Fanpage, Campaign, Group, TaskLog, FingerprintTest
from app.models.workflow_models import Workflow, WorkflowRun, WorkflowNodeExecution


class AccountFactory:
    _counter = 0

    @classmethod
    def create(cls, **overrides) -> Account:
        cls._counter += 1
        defaults = {
            "fb_email": f"fbuser{cls._counter}@example.com",
            "fb_password": "fbpassword123",
            "proxy_url": None,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return Account(**defaults)


class FanpageFactory:
    _counter = 0

    @classmethod
    def create(cls, **overrides) -> Fanpage:
        cls._counter += 1
        defaults = {
            "fanpage_url": f"https://www.facebook.com/testfanpage{cls._counter}",
            "fanpage_name": f"Test Fanpage {cls._counter}",
        }
        defaults.update(overrides)
        return Fanpage(**defaults)


class CampaignFactory:
    @staticmethod
    def create(**overrides) -> Campaign:
        defaults = {
            "name": "Test Campaign",
            "posts_per_day": 1,
            "base_interval_minutes": 840,
            "random_deviation_percent": 20.0,
            "active_hours_start": "00:00",
            "active_hours_end": "23:59",
            "active_days": [0, 1, 2, 3, 4, 5, 6],
            "status": "SZKIC",
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return Campaign(**defaults)


class GroupFactory:
    @staticmethod
    def create(**overrides) -> Group:
        defaults = {
            "url": "https://facebook.com/groups/test-group",
            "name": "Test Group",
            "content": "Test post content",
            "media_urls": None,
            "order": 0,
        }
        defaults.update(overrides)
        return Group(**defaults)


class TaskLogFactory:
    @staticmethod
    def create(**overrides) -> TaskLog:
        defaults = {
            "campaign_name": "Test Campaign",
            "status": "SUCCESS",
            "error_message": None,
            "screenshot_path": None,
            "planned_at": None,
            "retry_count": 0,
            "executed_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return TaskLog(**defaults)


class WorkflowFactory:
    _counter = 0

    @classmethod
    def create(cls, **overrides) -> Workflow:
        cls._counter += 1
        defaults = {
            "name": f"Test Workflow {cls._counter}",
            "description": "A test workflow",
            "status": "SZKIC",
            "graph_data": {
                "nodes": [
                    {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start", "config": {}}},
                    {"id": "node_2", "type": "end", "position": {"x": 300, "y": 0}, "data": {"label": "Koniec", "config": {}}},
                ],
                "edges": [{"id": "e1-2", "source": "node_1", "target": "node_2"}],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            },
        }
        defaults.update(overrides)
        return Workflow(**defaults)


class WorkflowRunFactory:
    @staticmethod
    def create(**overrides) -> WorkflowRun:
        defaults = {
            "status": "PENDING",
            "trigger_type": "manual",
            "variables": {},
        }
        defaults.update(overrides)
        return WorkflowRun(**defaults)


class WorkflowNodeExecutionFactory:
    @staticmethod
    def create(**overrides) -> WorkflowNodeExecution:
        defaults = {
            "node_id": "node_1",
            "node_type": "start",
            "status": "PENDING",
        }
        defaults.update(overrides)
        return WorkflowNodeExecution(**defaults)


class FingerprintTestFactory:
    @staticmethod
    def create(**overrides) -> FingerprintTest:
        defaults = {
            "status": "PENDING",
            "proxy_url_used": None,
            "results": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
        defaults.update(overrides)
        return FingerprintTest(**defaults)
