import pytest
import random
from unittest.mock import AsyncMock, MagicMock, patch

from app.workflow.node_registry import (
    get_node,
    _resolve_var,
    NodeExecutionError,
    StartNode,
    EndNode,
    WaitNode,
    IfElseNode,
    LoopNode,
    RandomChoiceNode,
    MergeNode,
    VariableNode,
    PostGroupNode,
    PostFanpageNode,
    LoginNode,
    WebhookNode,
)


class FakeContext:
    """Minimal ExecutionContext stub for unit tests."""

    def __init__(self, variables=None, fb_actions=None, account=None):
        self.run_id = 1
        self.variables = variables or {}
        self.node_outputs = {}
        self.current_node_id = "test_node"
        self.fb_actions = fb_actions
        self.account = account
        self.browser_manager = None
        self.page = None
        self._cancelled = False


class TestResolveVar:
    def test_simple_replacement(self):
        assert _resolve_var("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_multiple_replacements(self):
        result = _resolve_var("{{a}} and {{b}}", {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_missing_variable_kept(self):
        assert _resolve_var("{{unknown}}", {}) == "{{unknown}}"

    def test_no_template(self):
        assert _resolve_var("plain text", {"a": "b"}) == "plain text"

    def test_list_value_joins(self):
        result = _resolve_var("{{urls}}", {"urls": ["a.com", "b.com"]})
        assert result == "a.com\nb.com"

    def test_number_value_converted(self):
        assert _resolve_var("count: {{n}}", {"n": 42}) == "count: 42"

    def test_empty_string(self):
        assert _resolve_var("", {}) == ""


class TestGetNode:
    def test_get_known_node(self):
        node = get_node("start")
        assert node.node_type == "start"
        assert isinstance(node, StartNode)

    def test_get_all_registered_nodes(self):
        expected = [
            "start", "end", "login", "post_group", "post_fanpage",
            "like_page", "comment", "send_message", "wait", "if_else",
            "loop", "random_choice", "merge", "variable", "webhook",
        ]
        for node_type in expected:
            node = get_node(node_type)
            assert node.node_type == node_type

    def test_get_unknown_node_raises(self):
        with pytest.raises(NodeExecutionError, match="Unknown node type"):
            get_node("nonexistent_node")


class TestStartEndNodes:
    async def test_start_returns_started(self):
        ctx = FakeContext()
        node = get_node("start")
        result = await node.execute(ctx, {})
        assert result == {"status": "started"}

    async def test_end_returns_finished(self):
        ctx = FakeContext()
        node = get_node("end")
        result = await node.execute(ctx, {})
        assert result == {"status": "finished"}

    def test_start_no_retries(self):
        assert get_node("start").max_retries == 0

    def test_end_no_retries(self):
        assert get_node("end").max_retries == 0


class TestWaitNode:
    async def test_wait_seconds(self):
        ctx = FakeContext()
        node = get_node("wait")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await node.execute(ctx, {"duration": 5, "unit": "s"})
        mock_sleep.assert_called_once()
        assert result["waited"] == 5

    async def test_wait_minutes(self):
        ctx = FakeContext()
        node = get_node("wait")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await node.execute(ctx, {"duration": 2, "unit": "m"})
        assert result["waited"] == 120

    async def test_wait_hours(self):
        ctx = FakeContext()
        node = get_node("wait")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await node.execute(ctx, {"duration": 1, "unit": "h"})
        assert result["waited"] == 3600

    async def test_wait_random_variation(self):
        ctx = FakeContext()
        node = get_node("wait")
        random.seed(42)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await node.execute(ctx, {"duration": 10, "unit": "s", "random_variation": True})
        # With random_variation, actual wait should be between 8 and 12 seconds
        assert 8 <= result["waited"] <= 12

    async def test_wait_resume_skips(self):
        import time
        ctx = FakeContext()
        ctx.current_node_id = "wait_1"
        # Simulate a previously persisted wait_until in the past
        ctx.node_outputs["wait_1"] = {"wait_until": time.time() - 10}

        node = get_node("wait")
        result = await node.execute(ctx, {"duration": 999, "unit": "h"})
        assert result["skipped_resume"] is True
        assert result["waited"] == 0


class TestIfElseNode:
    async def test_eq_true(self):
        ctx = FakeContext(variables={"status": "success"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "status", "operator": "eq", "value": "success"})
        assert result["condition_result"] is True
        assert result["branch"] == "true"

    async def test_eq_false(self):
        ctx = FakeContext(variables={"status": "failed"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "status", "operator": "eq", "value": "success"})
        assert result["condition_result"] is False
        assert result["branch"] == "false"

    async def test_neq(self):
        ctx = FakeContext(variables={"x": "a"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "x", "operator": "neq", "value": "b"})
        assert result["condition_result"] is True

    async def test_gt(self):
        ctx = FakeContext(variables={"count": "10"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "count", "operator": "gt", "value": "5"})
        assert result["condition_result"] is True

    async def test_lt(self):
        ctx = FakeContext(variables={"count": "3"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "count", "operator": "lt", "value": "5"})
        assert result["condition_result"] is True

    async def test_gt_non_numeric(self):
        ctx = FakeContext(variables={"val": "abc"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "val", "operator": "gt", "value": "5"})
        assert result["condition_result"] is False

    async def test_contains(self):
        ctx = FakeContext(variables={"msg": "hello world"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "msg", "operator": "contains", "value": "world"})
        assert result["condition_result"] is True

    async def test_missing_variable(self):
        ctx = FakeContext(variables={})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "missing", "operator": "eq", "value": ""})
        assert result["condition_result"] is True  # "" == ""

    async def test_unknown_operator(self):
        ctx = FakeContext(variables={"x": "1"})
        node = get_node("if_else")
        result = await node.execute(ctx, {"variable": "x", "operator": "unknown_op", "value": "1"})
        assert result["condition_result"] is False

    async def test_sets_context_variable(self):
        ctx = FakeContext(variables={"x": "1"})
        ctx.current_node_id = "if_1"
        node = get_node("if_else")
        await node.execute(ctx, {"variable": "x", "operator": "eq", "value": "1"})
        assert ctx.variables["_condition_if_1"] is True


class TestLoopNode:
    async def test_first_iteration(self):
        ctx = FakeContext()
        ctx.current_node_id = "loop_1"
        node = get_node("loop")
        result = await node.execute(ctx, {"iterations": 3, "iterator_variable": "i"})
        assert result["iteration"] == 0
        assert result["done"] is False
        assert result["branch"] == "body"
        assert ctx.variables["i"] == 0

    async def test_done_when_iterations_reached(self):
        ctx = FakeContext(variables={"_loop_loop_1": 3})
        ctx.current_node_id = "loop_1"
        node = get_node("loop")
        result = await node.execute(ctx, {"iterations": 3})
        assert result["done"] is True
        assert result["branch"] == "done"

    async def test_mid_iteration(self):
        ctx = FakeContext(variables={"_loop_loop_1": 1})
        ctx.current_node_id = "loop_1"
        node = get_node("loop")
        result = await node.execute(ctx, {"iterations": 3})
        assert result["iteration"] == 1
        assert result["done"] is False


class TestRandomChoiceNode:
    async def test_returns_valid_choice(self):
        ctx = FakeContext()
        random.seed(42)
        node = get_node("random_choice")
        result = await node.execute(ctx, {"weights": [1, 1, 1]})
        assert result["chosen_index"] in (0, 1, 2)
        assert result["branch"].startswith("choice_")

    async def test_weighted_heavily(self):
        ctx = FakeContext()
        node = get_node("random_choice")
        # With weight 0 for second, should always pick first
        results = set()
        for _ in range(20):
            r = await node.execute(ctx, {"weights": [100, 0]})
            results.add(r["chosen_index"])
        assert results == {0}


class TestMergeNode:
    async def test_merge_returns_true(self):
        ctx = FakeContext()
        node = get_node("merge")
        result = await node.execute(ctx, {})
        assert result == {"merged": True}


class TestVariableNode:
    async def test_set_text_variable(self):
        ctx = FakeContext()
        node = get_node("variable")
        result = await node.execute(ctx, {"name": "greeting", "var_type": "text", "value": "Hello"})
        assert ctx.variables["greeting"] == "Hello"
        assert result["value"] == "Hello"

    async def test_set_number_variable(self):
        ctx = FakeContext()
        node = get_node("variable")
        result = await node.execute(ctx, {"name": "count", "var_type": "number", "value": "42"})
        assert ctx.variables["count"] == 42.0
        assert result["value"] == 42.0

    async def test_set_number_invalid_defaults_zero(self):
        ctx = FakeContext()
        node = get_node("variable")
        result = await node.execute(ctx, {"name": "x", "var_type": "number", "value": "abc"})
        assert ctx.variables["x"] == 0

    async def test_set_url_list_variable(self):
        ctx = FakeContext()
        node = get_node("variable")
        result = await node.execute(ctx, {
            "name": "urls",
            "var_type": "url_list",
            "value": "a.com\nb.com\nc.com",
        })
        assert ctx.variables["urls"] == ["a.com", "b.com", "c.com"]

    async def test_text_with_template_resolution(self):
        ctx = FakeContext(variables={"name": "World"})
        node = get_node("variable")
        result = await node.execute(ctx, {"name": "msg", "var_type": "text", "value": "Hello {{name}}"})
        assert ctx.variables["msg"] == "Hello World"


class TestValidateConfig:
    def test_post_group_requires_groups_and_content(self):
        node = get_node("post_group")
        errors = node.validate_config({})
        assert len(errors) == 2
        assert any("grupę" in e for e in errors)
        assert any("Treść" in e for e in errors)

    def test_post_group_valid(self):
        node = get_node("post_group")
        errors = node.validate_config({"group_url": "https://fb.com/groups/1", "content": "Hello"})
        assert errors == []

    def test_webhook_requires_url(self):
        node = get_node("webhook")
        errors = node.validate_config({})
        assert len(errors) == 1
        assert "URL" in errors[0]

    def test_webhook_valid(self):
        node = get_node("webhook")
        errors = node.validate_config({"url": "https://hook.site/abc"})
        assert errors == []

    def test_start_no_config_required(self):
        node = get_node("start")
        errors = node.validate_config({})
        assert errors == []


class TestFacebookNodesRequireSession:
    """All Facebook nodes should raise when fb_actions is None."""

    async def test_login_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("login")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {})

    async def test_post_group_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("post_group")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"group_url": "url", "content": "text"})

    async def test_post_fanpage_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("post_fanpage")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"fanpage_url": "url", "content": "text"})

    async def test_like_page_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("like_page")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"page_url": "url"})

    async def test_comment_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("comment")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"post_url": "url", "comment_text": "text"})

    async def test_send_message_no_session(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("send_message")
        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"profile_url": "url", "message_text": "text"})


class TestExecuteWithRetry:
    async def test_success_on_first_try(self):
        ctx = FakeContext()
        node = get_node("start")
        result = await node.execute_with_retry(ctx, {})
        assert result == {"status": "started"}

    async def test_retry_on_failure(self):
        node = get_node("login")
        mock_fb = AsyncMock()
        mock_account = MagicMock()
        mock_account.fb_password = "pass"
        mock_fb.login = AsyncMock(
            side_effect=[Exception("timeout"), Exception("timeout"), True]
        )
        ctx = FakeContext(fb_actions=mock_fb, account=mock_account)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await node.execute_with_retry(ctx, {})
        assert result["success"] is True
        assert mock_fb.login.call_count == 3

    async def test_max_retries_exceeded(self):
        node = get_node("login")
        mock_fb = AsyncMock()
        mock_account = MagicMock()
        mock_account.fb_password = "pass"
        mock_fb.login = AsyncMock(side_effect=Exception("always fails"))
        ctx = FakeContext(fb_actions=mock_fb, account=mock_account)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(NodeExecutionError, match="failed"):
                await node.execute_with_retry(ctx, {})
        assert mock_fb.login.call_count == 4  # 1 + 3 retries


class TestLoginNode:
    async def test_login_success(self):
        mock_fb = AsyncMock()
        mock_fb.login = AsyncMock(return_value=True)
        mock_account = MagicMock()
        mock_account.fb_password = "pass123"

        ctx = FakeContext(fb_actions=mock_fb, account=mock_account)
        node = get_node("login")
        result = await node.execute(ctx, {})

        assert result["success"] is True
        assert result["login_result"] == "success"
        assert ctx.variables["login_result"] == "success"

    async def test_login_checkpoint(self):
        mock_fb = AsyncMock()
        mock_fb.login = AsyncMock(return_value=False)
        mock_account = MagicMock()
        mock_account.fb_password = "pass123"

        ctx = FakeContext(fb_actions=mock_fb, account=mock_account)
        node = get_node("login")
        result = await node.execute(ctx, {})

        assert result["success"] is False
        assert result["login_result"] == "checkpoint"
        assert ctx.variables["login_result"] == "checkpoint"


class TestPostFanpageNodeMultiUrl:
    """Tests for PostFanpageNode multi-fanpage iteration."""

    async def test_single_url_backward_compat(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_url": "https://facebook.com/page1",
            "content": "Hello",
        })
        assert result["success"] is True
        assert result["fanpage_url"] == "https://facebook.com/page1"
        mock_fb.publish_on_fanpage.assert_called_once()

    async def test_multiple_urls(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_urls": [
                "https://facebook.com/page1",
                "https://facebook.com/page2",
                "https://facebook.com/page3",
            ],
            "content": "Multi post",
        })
        assert result["total"] == 3
        assert result["completed"] == 3
        assert result["failed"] == 0
        assert len(result["results"]) == 3
        assert mock_fb.publish_on_fanpage.call_count == 3

    async def test_multiple_urls_partial_failure(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(side_effect=[True, False, True])
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_urls": ["url1", "url2", "url3"],
            "content": "Test",
        })
        assert result["completed"] == 2
        assert result["failed"] == 1

    async def test_multiple_urls_with_exception(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(
            side_effect=[True, Exception("Network error"), True]
        )
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_urls": ["url1", "url2", "url3"],
            "content": "Test",
        })
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["results"][1]["error"] == "Network error"

    async def test_fanpage_urls_takes_priority_over_single(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_url": "https://facebook.com/ignored",
            "fanpage_urls": ["https://facebook.com/used1", "https://facebook.com/used2"],
            "content": "Test",
        })
        assert result["total"] == 2
        calls = [c.args[0] for c in mock_fb.publish_on_fanpage.call_args_list]
        assert "https://facebook.com/ignored" not in calls

    async def test_no_urls_raises(self):
        mock_fb = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        with pytest.raises(NodeExecutionError, match="Brak fanpage"):
            await node.execute(ctx, {"content": "Test"})

    async def test_no_session_raises(self):
        ctx = FakeContext(fb_actions=None)
        node = get_node("post_fanpage")

        with pytest.raises(NodeExecutionError, match="No browser session"):
            await node.execute(ctx, {"fanpage_url": "url", "content": "text"})

    def test_validate_config_fanpage_urls(self):
        node = get_node("post_fanpage")
        errors = node.validate_config({
            "fanpage_urls": ["https://facebook.com/page1"],
            "content": "Hello",
        })
        assert errors == []

    def test_validate_config_no_url(self):
        node = get_node("post_fanpage")
        errors = node.validate_config({"content": "Hello"})
        assert any("fanpage" in e.lower() for e in errors)

    def test_validate_config_no_content(self):
        node = get_node("post_fanpage")
        errors = node.validate_config({"fanpage_url": "https://facebook.com/page1"})
        assert any("treść" in e.lower() or "treś" in e for e in errors)


class TestPostFanpageNodeSchedule:
    """Tests for PostFanpageNode with per-fanpage scheduling."""

    async def test_fanpages_array_basic(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "https://facebook.com/page1", "content": "Post 1"},
                {"url": "https://facebook.com/page2", "content": "Post 2"},
            ],
        })
        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["failed"] == 0
        assert mock_fb.publish_on_fanpage.call_count == 2
        # Verify per-fanpage content
        calls = mock_fb.publish_on_fanpage.call_args_list
        assert calls[0].args[1] == "Post 1"
        assert calls[1].args[1] == "Post 2"

    async def test_per_fanpage_content_fallback(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "https://facebook.com/page1", "content": "Custom"},
                {"url": "https://facebook.com/page2", "content": ""},
            ],
            "default_content": "Default text",
        })
        assert result["completed"] == 2
        calls = mock_fb.publish_on_fanpage.call_args_list
        assert calls[0].args[1] == "Custom"
        assert calls[1].args[1] == "Default text"

    async def test_recurring_schedule_filter(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        # NOT test mode — schedule filter active
        node = get_node("post_fanpage")

        from datetime import datetime
        today = datetime.now().weekday()  # 0=Mon..6=Sun
        other_day = (today + 1) % 7  # A day that is NOT today

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "https://facebook.com/page1", "content": "Active", "recurring": True, "recurring_days": [today], "recurring_time": "00:00"},
                {"url": "https://facebook.com/page2", "content": "Skipped", "recurring": True, "recurring_days": [other_day], "recurring_time": "00:00"},
            ],
        })
        assert result["active"] == 1
        assert result["skipped"] == 1
        assert result["completed"] == 1
        assert mock_fb.publish_on_fanpage.call_count == 1

    async def test_test_mode_skips_schedule(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        from datetime import datetime
        other_day = (datetime.now().weekday() + 1) % 7

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "url1", "content": "A", "recurring": True, "recurring_days": [other_day]},
            ],
        })
        # In test mode, all fanpages are active regardless of schedule
        assert result["active"] == 1
        assert result["completed"] == 1

    async def test_per_fanpage_media_and_bg(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "url1", "content": "A", "background_style": "red", "media_files": []},
                {"url": "url2", "content": "B", "media_files": ["photo.jpg"]},
            ],
        })
        assert result["completed"] == 2
        calls = mock_fb.publish_on_fanpage.call_args_list
        assert calls[0].kwargs["background_style"] == "red"
        assert calls[1].kwargs["media_urls"] == ["photo.jpg"]

    async def test_skipped_result_when_no_active(self):
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        node = get_node("post_fanpage")

        from datetime import datetime
        other_day = (datetime.now().weekday() + 1) % 7

        result = await node.execute(ctx, {
            "fanpages": [
                {"url": "url1", "content": "A", "recurring": True, "recurring_days": [other_day]},
                {"url": "url2", "content": "B", "recurring": True, "recurring_days": [other_day]},
            ],
        })
        assert result["active"] == 0
        assert result["skipped"] == 2
        assert result["completed"] == 0
        assert mock_fb.publish_on_fanpage.call_count == 0
        assert ctx.variables["last_publish_result"] == "skipped"

    async def test_backward_compat_fanpage_urls(self):
        """Old config with fanpage_urls list should still work."""
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_urls": ["url1", "url2"],
            "content": "Old format",
        })
        assert result["total"] == 2
        assert result["completed"] == 2

    async def test_backward_compat_single_url(self):
        """Old config with single fanpage_url should still work."""
        mock_fb = AsyncMock()
        mock_fb.publish_on_fanpage = AsyncMock(return_value=True)
        ctx = FakeContext(fb_actions=mock_fb)
        ctx.variables["test_mode"] = True
        node = get_node("post_fanpage")

        result = await node.execute(ctx, {
            "fanpage_url": "https://facebook.com/page1",
            "content": "Old format",
        })
        assert result["success"] is True
        assert result["fanpage_url"] == "https://facebook.com/page1"

    def test_validate_config_new_format(self):
        node = get_node("post_fanpage")
        errors = node.validate_config({
            "fanpages": [{"url": "url1", "content": "Hello"}],
        })
        assert errors == []

    def test_validate_config_empty(self):
        node = get_node("post_fanpage")
        errors = node.validate_config({})
        assert len(errors) >= 1


class TestPostGroupNodePerGroupFanpage:
    """Tests for PostGroupNode per-group fanpage override."""

    async def test_global_fanpage_no_per_group(self):
        mock_fb = AsyncMock()
        mock_fb.switch_to_page_profile = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_fanpage = AsyncMock(return_value=True)
        mock_fb.publish_in_group = AsyncMock(return_value=True)
        mock_fb._current_page_name = None
        mock_fb.switch_to_personal_profile = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb, variables={"test_mode": True})
        node = get_node("post_group")

        result = await node.execute(ctx, {
            "groups": [
                {"url": "https://fb.com/groups/1"},
                {"url": "https://fb.com/groups/2"},
            ],
            "default_content": "Hello",
            "publish_as_fanpage": "https://facebook.com/myfanpage",
        })
        # Switch happens once before loop (no per-group overrides)
        mock_fb.switch_to_page_profile.assert_called_once_with("https://facebook.com/myfanpage")
        assert result["completed"] == 2

    async def test_per_group_fanpage_override(self):
        mock_fb = AsyncMock()
        mock_fb.switch_to_page_profile = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_fanpage = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_personal = AsyncMock(return_value=True)
        mock_fb.publish_in_group = AsyncMock(return_value=True)
        mock_fb._current_page_name = None
        mock_fb.switch_to_personal_profile = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb, variables={"test_mode": True})
        node = get_node("post_group")

        result = await node.execute(ctx, {
            "groups": [
                {"url": "https://fb.com/groups/1", "fanpage_url": "https://facebook.com/fanpageA"},
                {"url": "https://fb.com/groups/2", "fanpage_url": "https://facebook.com/fanpageB"},
            ],
            "default_content": "Hello",
        })
        # Two different fanpages = switch_to_page_profile called at least twice
        assert mock_fb.switch_to_page_profile.call_count >= 2
        assert result["completed"] == 2

    async def test_per_group_minimizes_switches(self):
        mock_fb = AsyncMock()
        mock_fb.switch_to_page_profile = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_fanpage = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_personal = AsyncMock(return_value=True)
        mock_fb.publish_in_group = AsyncMock(return_value=True)
        mock_fb._current_page_name = None
        mock_fb.switch_to_personal_profile = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb, variables={"test_mode": True})
        node = get_node("post_group")

        result = await node.execute(ctx, {
            "groups": [
                {"url": "https://fb.com/groups/1", "fanpage_url": "https://facebook.com/fpA"},
                {"url": "https://fb.com/groups/2", "fanpage_url": "https://facebook.com/fpA"},
                {"url": "https://fb.com/groups/3", "fanpage_url": "https://facebook.com/fpB"},
            ],
            "default_content": "Hello",
        })
        # Groups 1 and 2 share fpA — only 1 switch needed. Group 3 switches to fpB.
        # Total: 2 switch_to_page_profile calls (fpA, then personal+fpB)
        assert mock_fb.switch_to_page_profile.call_count == 2
        assert result["completed"] == 3

    async def test_per_group_empty_fanpage_uses_global(self):
        mock_fb = AsyncMock()
        mock_fb.switch_to_page_profile = AsyncMock(return_value=True)
        mock_fb.verify_identity_as_fanpage = AsyncMock(return_value=True)
        mock_fb.publish_in_group = AsyncMock(return_value=True)
        mock_fb._current_page_name = None
        mock_fb.switch_to_personal_profile = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb, variables={"test_mode": True})
        node = get_node("post_group")

        result = await node.execute(ctx, {
            "groups": [
                {"url": "https://fb.com/groups/1", "fanpage_url": ""},
                {"url": "https://fb.com/groups/2"},
            ],
            "default_content": "Hello",
            "publish_as_fanpage": "https://facebook.com/globalfp",
        })
        # Empty/missing per-group falls back to global — only 1 switch needed
        mock_fb.switch_to_page_profile.assert_called_once_with("https://facebook.com/globalfp")
        assert result["completed"] == 2

    async def test_switch_failure_skips_group(self):
        mock_fb = AsyncMock()
        mock_fb.switch_to_page_profile = AsyncMock(return_value=False)
        mock_fb.verify_identity_as_personal = AsyncMock(return_value=True)
        mock_fb.publish_in_group = AsyncMock(return_value=True)
        mock_fb._current_page_name = None
        mock_fb.switch_to_personal_profile = AsyncMock()
        ctx = FakeContext(fb_actions=mock_fb, variables={"test_mode": True})
        node = get_node("post_group")

        result = await node.execute(ctx, {
            "groups": [
                {"url": "https://fb.com/groups/1", "fanpage_url": "https://facebook.com/badfp"},
            ],
            "default_content": "Hello",
        })
        assert result["failed"] == 1
        assert result["completed"] == 0
