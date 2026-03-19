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

        email = context.account.fb_email if context.account else "?"
        logger.info("Logowanie do Facebook: %s", email)
        password = context.account.fb_password if context.account else ""
        success = await context.fb_actions.login(password)

        result = "success" if success else "checkpoint"
        context.variables["login_result"] = result
        logger.info("Login result: %s", result)
        return {"login_result": result, "success": success}

    def validate_config(self, config: dict) -> list[str]:
        return []


class _PublishNodeBase(BaseNode):
    """Shared scheduling + publish loop for PostGroupNode and PostFanpageNode."""

    _collection_key: str = ""   # "groups" or "fanpages"
    _item_label: str = ""       # "Grupa" or "Fanpage" (for logging)

    def _normalize_items(self, config: dict, items: list, context: "ExecutionContext") -> list:
        """Convert old config formats to items list. Override in subclass."""
        return items

    def _empty_error(self) -> str:
        return f"No {self._collection_key} configured"

    def _make_result(self, url: str, success: bool, item: dict, **extra) -> dict:
        return {"url": url, "success": success, "recurring": item.get("recurring", False), **extra}

    async def _pre_publish(self, context: "ExecutionContext", config: dict, items: list, state: dict):
        """Setup before publish loop (e.g. identity switch). Override if needed."""

    async def _post_publish(self, context: "ExecutionContext", state: dict):
        """Cleanup after publish loop. Override if needed."""

    async def _pre_item(self, context: "ExecutionContext", config: dict, item: dict,
                        index: int, total: int, state: dict) -> dict | None:
        """Per-item setup (e.g. identity switch). Returns error result dict or None."""
        return None

    async def _publish_item(self, context: "ExecutionContext", url: str, content: str,
                            bg: str | None, media: list, item: dict) -> bool:
        raise NotImplementedError

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        test_mode = context.variables.get("test_mode", False)
        items = config.get(self._collection_key, [])
        default_content = _resolve_var(
            config.get("default_content", "") or config.get("content", ""),
            context.variables,
        )

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        items = self._normalize_items(config, items, context)
        if not items:
            raise NodeExecutionError(self._empty_error())

        logger.info("%s: %d item(s), content=%d chars, test=%s",
                    self.node_type, len(items), len(default_content), test_mode)

        state = {}
        await self._pre_publish(context, config, items, state)

        try:
            if test_mode:
                active = items
                logger.info("Test mode — skipping schedule filter, all %d %s active",
                            len(items), self._collection_key)
            else:
                active = _filter_scheduled_items(items)

            results, completed, failed = [], 0, 0

            for i, item in enumerate(active):
                url = _resolve_var(item.get("url", ""), context.variables)
                if not url:
                    continue

                error = await self._pre_item(context, config, item, i, len(active), state)
                if error:
                    results.append(error)
                    failed += 1
                    continue

                item_content = item.get("content", "")
                content = _resolve_var(item_content, context.variables) if item_content else default_content

                if not test_mode:
                    planned_date = item.get("planned_date", "")
                    planned_time = item.get("planned_time", "")
                    if planned_date and planned_time:
                        await _wait_until_planned(planned_date, planned_time)
                    if item.get("recurring") and item.get("recurring_time"):
                        await _wait_until_recurring_time(
                            item["recurring_time"], item.get("recurring_jitter", 0))

                bg = item.get("background_style") or None
                media = item.get("media_files") or config.get("default_media_files") or []

                try:
                    logger.info("%s %d/%d: %s (bg=%s, media=%d)",
                                self._item_label, i + 1, len(active), url,
                                bg or "brak", len(media))
                    success = await self._publish_item(context, url, content, bg, media, item)
                    results.append(self._make_result(url, success, item))
                    if success:
                        completed += 1
                        logger.info("%s %d/%d: OPUBLIKOWANO", self._item_label, i + 1, len(active))
                    else:
                        failed += 1
                        logger.warning("%s %d/%d: NIEPOWODZENIE", self._item_label, i + 1, len(active))
                except Exception as exc:
                    logger.error("%s %d/%d (%s) error: %s",
                                 self._item_label, i + 1, len(active), url, exc)
                    results.append(self._make_result(url, False, item, error=str(exc)))
                    failed += 1

                if i < len(active) - 1:
                    delay = random.uniform(5, 10) if test_mode else random.uniform(3, 8)
                    logger.info("Pausing %.1fs between posts", delay)
                    await asyncio.sleep(delay)

            skipped = len(items) - len(active)

            if not active:
                logger.info("No %s active today (all %d skipped by schedule)",
                            self._collection_key, len(items))
                context.variables["last_publish_result"] = "skipped"
                return {
                    "total": len(items), "active": 0,
                    "completed": 0, "failed": 0, "skipped": skipped,
                    "results": [],
                }

            context.variables["last_publish_result"] = (
                "success" if failed == 0 else "partial" if completed > 0 else "failed"
            )
            return {
                "total": len(items), "active": len(active),
                "completed": completed, "failed": failed,
                "skipped": skipped, "results": results,
            }

        finally:
            await self._post_publish(context, state)


class PostGroupNode(_PublishNodeBase):
    node_type = "post_group"
    label = "Posty na grupach"
    category = "facebook"
    _collection_key = "groups"
    _item_label = "Grupa"

    def _normalize_items(self, config, items, context):
        if not items and config.get("group_url"):
            return [{"url": config["group_url"]}]
        return items

    def _empty_error(self):
        return "No groups configured"

    def _make_result(self, url, success, item, **extra):
        desired = extra.pop("fanpage_url", item.get("fanpage_url") or None)
        return {"url": url, "success": success, "recurring": item.get("recurring", False),
                "fanpage_url": desired, **extra}

    async def _pre_publish(self, context, config, items, state):
        publish_as_fanpage = config.get("publish_as_fanpage") or None
        global_fanpage = _resolve_var(publish_as_fanpage, context.variables) if publish_as_fanpage else None
        state["global_fanpage"] = global_fanpage
        state["current_fanpage"] = None

        if global_fanpage:
            has_per_group = any(g.get("fanpage_url") for g in items)
            if not has_per_group:
                logger.info("Przelaczanie na profil fanpage przed postami na grupach: %s", global_fanpage)
                if not await context.fb_actions.switch_to_page_profile(global_fanpage):
                    raise NodeExecutionError(f"Nie udalo sie przelaczac na fanpage: {global_fanpage}")
                state["current_fanpage"] = global_fanpage
                if not await context.fb_actions.verify_identity_as_fanpage():
                    raise NodeExecutionError("Weryfikacja tozsamosci nieudana — profil osobisty aktywny zamiast fanpage")
        else:
            if not await context.fb_actions.verify_identity_as_personal():
                raise NodeExecutionError("Wykryto aktywny profil fanpage zamiast osobistego — przerywam")

    async def _pre_item(self, context, config, item, index, total, state):
        global_fanpage = state["global_fanpage"]
        current_fanpage = state["current_fanpage"]
        group_fanpage_raw = item.get("fanpage_url") or None
        desired = _resolve_var(group_fanpage_raw, context.variables) if group_fanpage_raw else global_fanpage

        if desired != current_fanpage:
            if current_fanpage:
                await context.fb_actions.switch_to_personal_profile()
                context.fb_actions._current_page_name = None
                logger.info("Przywrocono profil osobisty przed zmiana fanpage")
            if desired:
                logger.info("Przelaczanie na fanpage: %s (grupa %d/%d)", desired, index + 1, total)
                if not await context.fb_actions.switch_to_page_profile(desired):
                    url = _resolve_var(item.get("url", ""), context.variables)
                    logger.error("Nie udalo sie przelaczac na fanpage %s — pomijam grupe %s", desired, url)
                    return self._make_result(url, False, item, error=f"Identity switch failed: {desired}")
            state["current_fanpage"] = desired
        return None

    async def _publish_item(self, context, url, content, bg, media, item):
        return await context.fb_actions.publish_on_group(
            url, content, media_urls=media or None, background_style=bg)

    async def _post_publish(self, context, state):
        if state.get("current_fanpage"):
            try:
                await context.fb_actions.switch_to_personal_profile()
                logger.info("Przywrocono profil osobisty po postach na grupach")
            except Exception as e:
                logger.warning("Nie udalo sie przywrocic profilu osobistego: %s", e)
            context.fb_actions._current_page_name = None

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        groups = config.get("groups", [])
        if not groups and not config.get("group_url"):
            errors.append("Dodaj przynajmniej jedną grupę")
        has_any_content = config.get("default_content") or config.get("content") or any(g.get("content") for g in groups)
        if not has_any_content:
            errors.append("Treść posta jest wymagana (domyślna lub per grupa)")
        fanpage = config.get("publish_as_fanpage", "")
        if fanpage and "facebook.com" not in fanpage:
            errors.append("URL fanpage musi zawierać facebook.com")
        return errors


class PostFanpageNode(_PublishNodeBase):
    node_type = "post_fanpage"
    label = "Posty na fanpage'ach"
    category = "facebook"
    _collection_key = "fanpages"
    _item_label = "Fanpage"

    def _normalize_items(self, config, items, context):
        if items:
            return items
        urls = config.get("fanpage_urls") or []
        if not urls:
            single = _resolve_var(config.get("fanpage_url", ""), context.variables)
            if single:
                urls = [single]
        if urls:
            old_bg = config.get("background_style") or ""
            old_media = config.get("media_files") or []
            return [{"url": u, "content": "", "background_style": old_bg, "media_files": old_media} for u in urls]
        return []

    def _empty_error(self):
        return "Brak fanpage'y — skonfiguruj przynajmniej jeden"

    def _make_result(self, url, success, item, **extra):
        return {"fanpage_url": url, "success": success, "recurring": item.get("recurring", False), **extra}

    async def _publish_item(self, context, url, content, bg, media, item):
        return await context.fb_actions.publish_on_fanpage(
            url, content, background_style=bg, media_urls=media or None)

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        result = await super().execute(context, config)
        # Backward compat for single-URL old config
        if not config.get("fanpages") and len(result.get("results", [])) == 1:
            r = result["results"][0]
            return {"success": r["success"], "fanpage_url": r["fanpage_url"]}
        return result

    def validate_config(self, config: dict) -> list[str]:
        errors = []
        fanpages = config.get("fanpages", [])
        has_urls = bool(config.get("fanpage_urls"))
        has_single = bool(config.get("fanpage_url"))
        if not fanpages and not has_urls and not has_single:
            errors.append("Dodaj przynajmniej jeden fanpage")
        has_any_content = (
            config.get("default_content") or config.get("content")
            or any(fp.get("content") for fp in fanpages)
        )
        if not has_any_content:
            errors.append("Treść posta jest wymagana (domyślna lub per fanpage)")
        return errors


class LikePageNode(BaseNode):
    node_type = "like_page"
    label = "Polub stronę"
    category = "facebook"

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        page_url = _resolve_var(config.get("page_url", ""), context.variables)

        if not context.fb_actions:
            raise NodeExecutionError("No browser session")

        logger.info("Polubienie strony: %s", page_url)
        success = await context.fb_actions.like_page(page_url)
        logger.info("LikePage result: success=%s", success)
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

        logger.info("Komentarz na: %s (tresc: %d znakow)", post_url, len(comment_text))
        success = await context.fb_actions.comment_on_post(post_url, comment_text)
        logger.info("Comment result: success=%s", success)
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

        logger.info("Wiadomosc do: %s (tresc: %d znakow)", profile_url, len(message_text))
        success = await context.fb_actions.send_message(profile_url, message_text)
        logger.info("SendMessage result: success=%s", success)
        return {"success": success}


# ── Flow Control Nodes ──

class WaitNode(BaseNode):
    node_type = "wait"
    label = "Czekaj"
    category = "flow"
    max_retries = 0

    async def execute(self, context: "ExecutionContext", config: dict) -> dict:
        test_mode = context.variables.get("test_mode", False)
        duration = config.get("duration", 1)
        unit = config.get("unit", "s")

        multiplier = {"s": 1, "m": 60, "h": 3600}.get(unit, 1)
        total_seconds = duration * multiplier

        if config.get("random_variation"):
            total_seconds *= random.uniform(0.8, 1.2)

        # Test mode — short delay instead of full wait
        if test_mode:
            short = random.uniform(5, 10)
            logger.info("Test mode — waiting %.1fs instead of %.1fs", short, total_seconds)
            await asyncio.sleep(short)
            return {"waited": short, "skipped_test_mode": True}

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

        branch = "true" if result else "false"
        logger.info("Warunek: %s %s %s → %s (branch=%s)", variable, operator, expected, actual, branch)

        # Return which branch to follow: "true" or "false" handle ID
        context.variables[f"_condition_{context.current_node_id}"] = result
        return {"condition_result": result, "branch": branch}


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
        logger.info("Petla: iteracja %d/%d (%s=%d, branch=%s)",
                    current, iterations, iterator_var, current, "done" if done else "body")
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
        logger.info("Losowy wybor: index=%d z %d opcji (wagi=%s)", chosen, len(weights), weights)
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
        logger.info("Zmienna: %s = %s (typ=%s)", name, str(value)[:100], var_type)
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

        logger.info("Webhook: %s %s", method, url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url)
            elif method == "PUT":
                resp = await client.put(url, content=body, headers={"Content-Type": "application/json"})
            else:
                resp = await client.post(url, content=body, headers={"Content-Type": "application/json"})

        logger.info("Webhook response: %d (%d bytes)", resp.status_code, len(resp.text))
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

def _filter_scheduled_items(items: list[dict]) -> list[dict]:
    """Filter items to only those active today.

    - Non-recurring items: always included (their planned_date handles timing)
    - Recurring items: included only if today's weekday is in recurring_days
      (0=Monday ... 6=Sunday, ISO weekday)
    """
    from datetime import datetime
    today_weekday = datetime.now().weekday()  # 0=Monday ... 6=Sunday

    active = []
    for item in items:
        if not item.get("recurring"):
            active.append(item)
            continue
        recurring_days = item.get("recurring_days", [])
        if not recurring_days or today_weekday in recurring_days:
            active.append(item)
        else:
            logger.debug(
                "Skipping recurring item %s — today is %d, scheduled for %s",
                item.get("url", "?"), today_weekday, recurring_days,
            )
    return active


async def _wait_until_recurring_time(recurring_time: str, jitter_minutes: int = 0) -> None:
    """Wait until the recurring_time (HH:MM) today, with random jitter.

    jitter_minutes: max deviation in minutes (±).  E.g. 15 means the actual
    publish time will be anywhere from -15 to +15 minutes around recurring_time.
    """
    from datetime import datetime, timedelta
    try:
        now = datetime.now()
        h, m = map(int, recurring_time.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)

        # Apply random jitter
        if jitter_minutes > 0:
            offset = random.uniform(-jitter_minutes, jitter_minutes)
            target += timedelta(minutes=offset)
            logger.info("Recurring time %s with jitter ±%d min → target %s", recurring_time, jitter_minutes, target.strftime("%H:%M"))

        wait_secs = (target - now).total_seconds()
        if wait_secs > 0:
            logger.info("Waiting %.0f seconds until recurring time", wait_secs)
            await asyncio.sleep(wait_secs)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid recurring_time format (%s): %s", recurring_time, exc)


async def _wait_until_planned(planned_date: str, planned_time: str) -> None:
    """Wait until planned date+time before executing.  Skip if already past."""
    from datetime import datetime
    try:
        target = datetime.strptime(f"{planned_date} {planned_time}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        wait_secs = (target - now).total_seconds()
        if wait_secs > 0:
            logger.info("Waiting %.0f seconds until planned time %s %s", wait_secs, planned_date, planned_time)
            await asyncio.sleep(wait_secs)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid planned time format (%s %s): %s", planned_date, planned_time, exc)


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
