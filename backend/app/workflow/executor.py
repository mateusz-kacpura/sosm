"""Resumable DAG executor — walks workflow graph, survives restarts."""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.workflow_models import Workflow, WorkflowRun, WorkflowNodeExecution
from app.models.models import Account
from app.bot.browser_manager import BrowserManager
from app.bot.actions import FBActions
from .node_registry import get_node, NodeExecutionError

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Shared state for a workflow run."""

    def __init__(
        self,
        run_id: int,
        account: Optional[Account],
        browser_manager: Optional[BrowserManager],
        page,
        fb_actions: Optional[FBActions],
    ):
        self.run_id = run_id
        self.account = account
        self.browser_manager = browser_manager
        self.page = page
        self.fb_actions = fb_actions
        self.variables: dict = {}
        self.node_outputs: dict[str, dict] = {}  # node_id -> output_data
        self.current_node_id: str = ""
        self._cancelled = False

    @property
    def cancelled(self):
        return self._cancelled


class WorkflowExecutor:
    """Walks a DAG and executes nodes in topological order.

    Supports resuming interrupted runs: on restart, completed nodes are
    skipped and their outputs are rehydrated into context.
    """

    async def execute(
        self,
        workflow_id: int,
        run_id: int,
        variables: dict | None = None,
        resume: bool = False,
    ):
        """Execute or resume a workflow run."""
        run_t0 = time.monotonic()
        logger.info(
            "=== Workflow %d run %d %s ===",
            workflow_id, run_id, "RESUME" if resume else "START",
        )

        async with async_session_factory() as db:
            # Load workflow and run
            wf = await db.get(Workflow, workflow_id)
            if not wf:
                logger.error("Workflow %d not found", workflow_id)
                return

            run = await db.get(WorkflowRun, run_id)
            if not run:
                logger.error("WorkflowRun %d not found", run_id)
                return

            # Load account — from workflow.account_id, Login node config, or sole account
            account = None
            account_id = wf.account_id
            if not account_id:
                # Auto-detect from first login node in the graph
                account_id = self._find_login_account_id(wf.graph_data)
                if account_id:
                    logger.info("Auto-detected account_id=%d from Login node config", account_id)
            if not account_id:
                # Fallback: use the only account if exactly one exists
                all_accounts = (await db.execute(select(Account))).scalars().all()
                if len(all_accounts) == 1:
                    account_id = all_accounts[0].id
                    logger.info("Auto-selected sole account id=%d", account_id)
            if account_id:
                account = await db.get(Account, account_id)
            if account:
                logger.info("Account: id=%d email=%s profile=%s",
                            account.id, account.fb_email, account.browser_profile_id)
            else:
                logger.warning("No account resolved — Facebook nodes will fail")

            # Use graph snapshot from run (immutable)
            graph_data = run.graph_snapshot or wf.graph_data
            if not graph_data or not graph_data.get("nodes"):
                run.status = "FAILED"
                run.error_message = "Empty graph"
                await db.commit()
                return

            # Parse graph
            nodes_map, adjacency, reverse_adj = self._parse_graph(graph_data)

            # Topological sort (also detects cycles)
            try:
                topo_order = self._topological_sort(nodes_map, adjacency)
            except ValueError as e:
                run.status = "FAILED"
                run.error_message = str(e)
                await db.commit()
                logger.error("Topological sort failed: %s", e)
                return

            # Log execution plan
            plan = []
            for nid in topo_order:
                nd = nodes_map[nid].get("data", {})
                ntype = nd.get("type") or nodes_map[nid].get("type", "?")
                plan.append(ntype)
            logger.info("Execution plan (%d nodes): %s", len(plan), " → ".join(plan))

            # Mark run as RUNNING
            run.status = "RUNNING"
            run.started_at = datetime.now(timezone.utc)
            if variables:
                run.variables = variables
            await db.commit()

            # Hydrate context from previous node executions (resume support)
            completed_nodes: set[str] = set()
            if resume and run.variables:
                variables = run.variables

            context_vars = dict(variables or {})
            if resume:
                result = await db.execute(
                    select(WorkflowNodeExecution)
                    .where(WorkflowNodeExecution.run_id == run_id)
                )
                for ne in result.scalars().all():
                    if ne.status == "COMPLETED":
                        completed_nodes.add(ne.node_id)
                        if ne.output_data:
                            context_vars.update(
                                {k: v for k, v in ne.output_data.items() if not k.startswith("_")}
                            )
                    elif ne.status == "RUNNING":
                        # Crashed mid-execution — mark as failed, will retry
                        ne.status = "FAILED"
                        ne.error_message = "Interrupted by restart"
                        ne.completed_at = datetime.now(timezone.utc)
                await db.commit()

            # Start browser if we have an account
            browser_manager = None
            page = None
            fb_actions = None

            if account:
                logger.info("Starting browser for account %d...", account.id)
                browser_manager = BrowserManager(
                    account.id,
                    donut_profile_id=account.browser_profile_id,
                )
                try:
                    backup_cookies = account.session_cookies_backup or None
                    browser_t0 = time.monotonic()
                    page = await browser_manager.start(backup_cookies=backup_cookies)
                    fb_actions = FBActions(page, account.fb_email)
                    logger.info("Browser started in %.1fs", time.monotonic() - browser_t0)
                except Exception as e:
                    run.status = "FAILED"
                    run.error_message = f"Browser start failed: {e}"
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.error("Browser start failed: %s", e)
                    return

            ctx = ExecutionContext(
                run_id=run_id,
                account=account,
                browser_manager=browser_manager,
                page=page,
                fb_actions=fb_actions,
            )
            ctx.variables = context_vars

            try:
                await self._walk_dag(ctx, topo_order, nodes_map, adjacency, completed_nodes, db, run)
            except asyncio.CancelledError:
                logger.info("Workflow %d run %d cancelled via task.cancel()", workflow_id, run_id)
                run.status = "CANCELLED"
            except Exception as e:
                logger.exception("Workflow %d run %d failed: %s", workflow_id, run_id, e)
                run.status = "FAILED"
                run.error_message = str(e)[:1000]
            finally:
                # Save session cookies if possible
                if browser_manager and page and account:
                    try:
                        cookies = await browser_manager.extract_session_cookies(page)
                        if cookies:
                            account.session_cookies_backup = cookies
                            logger.info("Session cookies saved (%d cookies)", len(cookies))
                    except Exception as e:
                        logger.warning("Failed to save session cookies: %s", e)

                # Stop browser
                if browser_manager:
                    try:
                        await browser_manager.stop()
                        logger.info("Browser stopped")
                    except Exception as e:
                        logger.warning("Error stopping browser: %s", e)

                # Final status
                if run.status == "RUNNING":
                    run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
                run.variables = ctx.variables
                await db.commit()

                elapsed = time.monotonic() - run_t0
                logger.info(
                    "=== Workflow %d run %d %s (%.1fs) ===",
                    workflow_id, run_id, run.status, elapsed,
                )

    async def _walk_dag(
        self,
        ctx: ExecutionContext,
        topo_order: list[str],
        nodes_map: dict,
        adjacency: dict,
        completed_nodes: set[str],
        db: AsyncSession,
        run: WorkflowRun,
    ):
        """Walk nodes in topological order, handling branching and loops."""
        skipped_nodes: set[str] = set()  # Nodes skipped due to branch conditions
        branch_decisions: dict[str, str] = {}  # node_id -> chosen handle

        for node_id in topo_order:
            # Check cancellation
            await db.refresh(run)
            if run.status == "CANCELLED":
                ctx._cancelled = True
                return

            # Skip completed (resume) or skipped (branch) nodes
            if node_id in completed_nodes:
                # Reload output data into context
                result = await db.execute(
                    select(WorkflowNodeExecution)
                    .where(
                        WorkflowNodeExecution.run_id == ctx.run_id,
                        WorkflowNodeExecution.node_id == node_id,
                        WorkflowNodeExecution.status == "COMPLETED",
                    )
                )
                ne = result.scalar_one_or_none()
                if ne and ne.output_data:
                    ctx.node_outputs[node_id] = ne.output_data
                nd = nodes_map[node_id].get("data", {})
                ntype = nd.get("type") or nodes_map[node_id].get("type", "?")
                logger.info("  [%s] SKIP (already completed on resume)", ntype)
                continue

            if node_id in skipped_nodes:
                nd = nodes_map[node_id].get("data", {})
                ntype = nd.get("type") or nodes_map[node_id].get("type", "unknown")
                logger.info("  [%s] SKIP (branch not taken)", ntype)
                await self._record_node_execution(
                    db, ctx.run_id, node_id, ntype, "SKIPPED",
                )
                continue

            node_info = nodes_map[node_id]
            node_data = node_info.get("data", {})
            node_type = node_data.get("type") or node_info.get("type", "unknown")
            config = node_data.get("config", {})

            ctx.current_node_id = node_id

            # Execute node
            node_impl = get_node(node_type)
            ne = await self._record_node_execution(
                db, ctx.run_id, node_id, node_type, "RUNNING",
                input_data=config,
            )

            logger.info("  [%s] START", node_type)
            node_t0 = time.monotonic()

            try:
                output = await node_impl.execute_with_retry(ctx, config)
                ne.status = "COMPLETED"
                ne.output_data = output
                ne.completed_at = datetime.now(timezone.utc)
                ctx.node_outputs[node_id] = output
                node_dt = time.monotonic() - node_t0
                logger.info("  [%s] COMPLETED (%.1fs) → %s", node_type, node_dt, _summarize_output(output))
            except (NodeExecutionError, Exception) as e:
                ne.status = "FAILED"
                ne.error_message = str(e)[:1000]
                ne.completed_at = datetime.now(timezone.utc)
                node_dt = time.monotonic() - node_t0
                logger.error("  [%s] FAILED (%.1fs): %s", node_type, node_dt, e)
                await db.commit()
                raise

            # Handle branching decisions
            branch = output.get("branch")
            if branch and node_type in ("if_else", "loop", "random_choice"):
                branch_decisions[node_id] = branch
                # Mark nodes on non-taken branches as skipped
                for target_id, edge_data in adjacency.get(node_id, []):
                    edge_handle = edge_data.get("sourceHandle", "default")
                    if edge_handle != branch and edge_handle != "default":
                        self._mark_subtree_skipped(target_id, adjacency, skipped_nodes, completed_nodes)

            # Handle loop iteration advancement
            if node_type == "loop" and not output.get("done"):
                loop_key = f"_loop_{node_id}"
                ctx.variables[loop_key] = ctx.variables.get(loop_key, 0) + 1

            # Checkpoint: persist variables after each node
            run.variables = ctx.variables
            await db.commit()

    def _mark_subtree_skipped(
        self, start_id: str, adjacency: dict,
        skipped: set[str], completed: set[str],
    ):
        """BFS to mark all nodes in a subtree as skipped."""
        queue = [start_id]
        while queue:
            nid = queue.pop(0)
            if nid in completed or nid in skipped:
                continue
            skipped.add(nid)
            for target_id, _ in adjacency.get(nid, []):
                queue.append(target_id)

    async def _record_node_execution(
        self, db: AsyncSession, run_id: int, node_id: str,
        node_type: str, status: str, input_data: dict | None = None,
    ) -> WorkflowNodeExecution:
        """Create or update a node execution record."""
        # Check if exists (resume case)
        result = await db.execute(
            select(WorkflowNodeExecution)
            .where(
                WorkflowNodeExecution.run_id == run_id,
                WorkflowNodeExecution.node_id == node_id,
            )
        )
        ne = result.scalar_one_or_none()

        if ne:
            ne.status = status
            if status == "RUNNING":
                ne.started_at = datetime.now(timezone.utc)
                ne.error_message = None
                ne.output_data = None
        else:
            ne = WorkflowNodeExecution(
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                status=status,
                input_data=input_data,
                started_at=datetime.now(timezone.utc) if status == "RUNNING" else None,
            )
            db.add(ne)

        await db.commit()
        await db.refresh(ne)
        return ne

    @staticmethod
    def _find_login_account_id(graph_data: dict | None) -> int | None:
        """Find account_id from the first Login node's config in the graph."""
        if not graph_data:
            return None
        for node in graph_data.get("nodes", []):
            node_type = node.get("data", {}).get("type") or node.get("type")
            if node_type == "login":
                account_id = node.get("data", {}).get("config", {}).get("account_id")
                if account_id:
                    return int(account_id)
        return None

    @staticmethod
    def _parse_graph(graph_data: dict):
        """Parse React Flow graph_data into working structures."""
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        nodes_map = {n["id"]: n for n in nodes}
        adjacency: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        reverse_adj: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src and tgt:
                adjacency[src].append((tgt, edge))
                reverse_adj[tgt].append(src)

        return nodes_map, dict(adjacency), dict(reverse_adj)

    @staticmethod
    def _topological_sort(nodes_map: dict, adjacency: dict) -> list[str]:
        """Kahn's algorithm. Raises ValueError if cycle detected."""
        in_degree = {nid: 0 for nid in nodes_map}
        for src, targets in adjacency.items():
            for tgt, _ in targets:
                if tgt in in_degree:
                    in_degree[tgt] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for target, _ in adjacency.get(node, []):
                if target in in_degree:
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)

        if len(result) != len(nodes_map):
            raise ValueError("Graf zawiera cykl — workflow musi być acykliczny")

        return result

    async def resume_interrupted_runs(self):
        """Called at app startup — resume any RUNNING workflows."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(WorkflowRun).where(WorkflowRun.status == "RUNNING")
            )
            interrupted_runs = result.scalars().all()

            for run in interrupted_runs:
                logger.info(
                    "Resuming interrupted workflow run %d (workflow %d)",
                    run.id, run.workflow_id,
                )
                from app import task_runner
                await task_runner.submit_workflow_task(
                    run.workflow_id, run.id, run.variables, resume=True,
                )


def _summarize_output(output: dict) -> str:
    """Create a short summary of node output for logging."""
    if not output:
        return "{}"
    parts = []
    for key in ("success", "login_result", "status", "completed", "failed",
                "total", "branch", "waited", "chosen_index"):
        if key in output:
            parts.append(f"{key}={output[key]}")
    if not parts:
        return str({k: v for k, v in list(output.items())[:3]})
    return ", ".join(parts)
