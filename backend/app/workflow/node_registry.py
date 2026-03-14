"""Node type definitions with execution logic and per-node retry."""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .executor import ExecutionContext

logger = logging.getLogger(__name__)

RETRY_DELAYS = [5, 15, 30]  # seconds, exponential backoff


class NodeExecutionError(Exception):
    """Raised when a node fails execution."""
    pass


class BaseNode(ABC):
    """Base class for all workflow node types."""

    node_type: str = ""
    label: str = ""
    category: str = ""  # trigger, facebook, flow, utility
    max_retries: int = 3

    @abstractmethod
    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        """Execute node logic. Returns output_data dict."""
        pass

    async def execute_with_retry(self, context: "ExecutionContext", config: dict) -> dict:
        """Execute with exponential backoff retry."""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self.execute(context, config)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.warning(
                        "Node %s failed (attempt %d/%d), retry in %ds: %s",
                        self.node_type, attempt + 1, self.max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("Node %s failed after %d retries: %s", self.node_type, self.max_retries, exc)
        raise NodeExecutionError(f"Node {self.node_type} failed: {last_error}")

    def validate_config(self, config: dict) -> list[str]:
        """Validate node configuration. Returns list of error messages."""
        return []


# ── Trigger Nodes ──

class StartNode(BaseNode):
    node_type = "start"
    label = "Start"
    category = "trigger"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        return {"status": "started"}


class EndNode(BaseNode):
    node_type = "end"
    label = "Koniec"
    category = "trigger"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        return {"status": "finished"}


# ── Facebook Action Nodes ──

class LoginNode(BaseNode):
    node_type = "login"
    label = "Logowanie FB"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        if not context.fb_actions:
            raise NodeExecutionError("No browser session — add a Login node first")

        password = context.account.fb_password if context.account else ""
        success = await context.fb_actions.login(password)

        result = "success" if success else "checkpoint"
        context.variables["login_result"] = result
        return {"login_result": result, "success": success}

    def validate_config(self, config: dict) -> list[str]:
        return []


class PostGroupNode(BaseNode):
    node_type = "post_group"
    label = "Post na grupie"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        group_url = _resolve_var(config.get("group_url", ""), context.variables)
        content = _resolve_var(config.get("content", ""), context.variables)
        bg_style = config.get("background_style") or None

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        success = await context.fb_actions.publish_on_group(group_url, content, bg_style)
        context.variables["last_publish_result"] = "success" if success else "failed"
        return {"success": success, "group_url": group_url}

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        if not config.get("group_url"):
            errors.append("URL grupy jest wymagany")
        if not config.get("content"):
            errors.append("Treść posta jest wymagana")
        return errors


class PostFanpageNode(BaseNode):
    node_type = "post_fanpage"
    label = "Post na fanpage"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        fanpage_url = _resolve_var(config.get("fanpage_url", ""), context.variables)
        content = _resolve_var(config.get("content", ""), context.variables)

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        success = await context.fb_actions.publish_on_fanpage(fanpage_url, content)
        return {"success": success, "fanpage_url": fanpage_url}


class LikePageNode(BaseNode):
    node_type = "like_page"
    label = "Polub stronę"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        page_url = _resolve_var(config.get("page_url", ""), context.variables)

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        success = await context.fb_actions.like_page(page_url)
        return {"success": success, "page_url": page_url}


class CommentNode(BaseNode):
    node_type = "comment"
    label = "Komentarz"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        post_url = _resolve_var(config.get("post_url", ""), context.variables)
        comment_text = _resolve_var(config.get("comment_text", ""), context.variables)

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        success = await context.fb_actions.comment_on_post(post_url, comment_text)
        return {"success": success}


class SendMessageNode(BaseNode):
    node_type = "send_message"
    label = "Wyślij wiadomość"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        profile_url = _resolve_var(config.get("profile_url", ""), context.variables)
        message_text = _resolve_var(config.get("message_text", ""), context.variables)

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        success = await context.fb_actions.send_message(profile_url, message_text)
        return {"success": success}


# ── Flow Control Nodes ──

class WaitNode(BaseNode):
    node_type = "wait"
    label = "Czekaj"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        duration = config.get("duration", 1)
        unit = config.get("unit", "s")

        multiplier = {"s": 1, "m": 60, "h": 3600}.get(unit, 1)
        total_seconds = duration * multiplier

        if config.get("random_variation"):
            total_seconds *= random.uniform(0.8, 1.2)

        # Check if resuming from a previously persisted wait
        wait_until = context.node_outputs.get(context.current_node_id, {}).get("wait_until")
        if wait_until:
            import time
            remaining = wait_until - time.time()
            if remaining <= 0:
                return {"waited": 0, "skipped_resume": True}
            total_seconds = remaining

        import time
        wait_until_ts = time.time() + total_seconds

        logger.info("Waiting %.1f seconds", total_seconds)
        await asyncio.sleep(total_seconds)
        return {"waited": total_seconds, "wait_until": wait_until_ts}


class IfElseNode(BaseNode):
    node_type = "if_else"
    label = "Warunek"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        variable = config.get("variable", "")
        operator = config.get("operator", "eq")
        expected = config.get("value", "")

        actual = str(context.variables.get(variable, ""))

        if operator == "eq":
            result = actual == expected
        elif operator == "neq":
            result = actual != expected
        elif operator == "gt":
            try:
                result = float(actual) > float(expected)
            except ValueError:
                result = False
        elif operator == "lt":
            try:
                result = float(actual) < float(expected)
            except ValueError:
                result = False
        elif operator == "contains":
            result = expected in actual
        else:
            result = False

        # Return which branch to follow: "true" or "false" handle ID
        context.variables[f"_condition_{context.current_node_id}"] = result
        return {"condition_result": result, "branch": "true" if result else "false"}


class LoopNode(BaseNode):
    node_type = "loop"
    label = "Pętla"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        iterations = config.get("iterations", 1)
        iterator_var = config.get("iterator_variable", "i")

        # Get current iteration from persisted variables
        loop_key = f"_loop_{context.current_node_id}"
        current = context.variables.get(loop_key, 0)

        context.variables[iterator_var] = current
        context.variables[loop_key] = current

        done = current >= iterations
        return {
            "iteration": current,
            "total": iterations,
            "done": done,
            "branch": "done" if done else "body",
        }


class RandomChoiceNode(BaseNode):
    node_type = "random_choice"
    label = "Losowy wybór"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        weights = config.get("weights", [1, 1])
        chosen = random.choices(range(len(weights)), weights=weights, k=1)[0]
        return {"chosen_index": chosen, "branch": f"choice_{chosen}"}


class MergeNode(BaseNode):
    node_type = "merge"
    label = "Złącz"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        return {"merged": True}


# ── Utility Nodes ──

class VariableNode(BaseNode):
    node_type = "variable"
    label = "Zmienna"
    category = "utility"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        name = config.get("name", "")
        var_type = config.get("var_type", "text")
        raw_value = config.get("value", "")

        if var_type == "url_list":
            value = [line.strip() for line in raw_value.split("\n") if line.strip()]
        elif var_type == "number":
            try:
                value = float(raw_value)
            except ValueError:
                value = 0
        else:
            value = _resolve_var(raw_value, context.variables)

        context.variables[name] = value
        return {"name": name, "value": value}


class WebhookNode(BaseNode):
    node_type = "webhook"
    label = "Webhook"
    category = "utility"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        import httpx

        url = _resolve_var(config.get("url", ""), context.variables)
        method = config.get("method", "POST").upper()
        body_template = config.get("body_template", "")
        body = _resolve_var(body_template, context.variables) if body_template else None

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url)
            elif method == "PUT":
                resp = await client.put(url, content=body, headers={"Content-Type": "application/json"})
            else:
                resp = await client.post(url, content=body, headers={"Content-Type": "application/json"})

        return {"status_code": resp.status_code, "response_body": resp.text[:500]}

    def validate_config(self, config: dict) -> list[str]:
        if not config.get("url"):
            return ["URL webhook jest wymagany"]
        return []


# ── Registry ──

_REGISTRY: dict[str, BaseNode] = {}


def _register(cls: type[BaseNode]):
    instance = cls()
    _REGISTRY[instance.node_type] = instance
    return cls


# Register all nodes
for _cls in [
    StartNode, EndNode,
    LoginNode, PostGroupNode, PostFanpageNode, LikePageNode, CommentNode, SendMessageNode,
    WaitNode, IfElseNode, LoopNode, RandomChoiceNode, MergeNode,
    VariableNode, WebhookNode,
]:
    _register(_cls)


def get_node(node_type: str) -> BaseNode:
    """Get node implementation by type."""
    node = _REGISTRY.get(node_type)
    if not node:
        raise NodeExecutionError(f"Unknown node type: {node_type}")
    return node


# ── Helpers ──

def _resolve_var(template: str, variables: dict) -> str:
    """Resolve {{variable}} references in a string."""
    import re
    def replacer(match):
        var_name = match.group(1)
        value = variables.get(var_name, match.group(0))
        if isinstance(value, list):
            return "\n".join(str(v) for v in value)
        return str(value)
    return re.sub(r"\{\{(\w+)\}\}", replacer, template)
