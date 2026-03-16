from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.core.database import get_db
from app.models.workflow_models import Workflow, WorkflowRun, WorkflowNodeExecution
from app.models.workflow_schemas import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListItem,
    WorkflowRunCreate, WorkflowRunResponse, NodeExecutionResponse,
)

router = APIRouter()

# Available node type definitions for the frontend palette
NODE_TYPES = [
    # Trigger
    {"type": "start", "label": "Start", "category": "trigger",
     "description": "Punkt startowy workflow", "config_schema": {}},
    {"type": "end", "label": "Koniec", "category": "trigger",
     "description": "Punkt końcowy workflow", "config_schema": {}},
    # Facebook Actions
    {"type": "login", "label": "Logowanie FB", "category": "facebook",
     "description": "Zaloguj się na konto Facebook",
     "config_schema": {"account_id": "number"}},
    {"type": "post_group", "label": "Post na grupie", "category": "facebook",
     "description": "Opublikuj post w grupie Facebook",
     "config_schema": {"group_url": "string", "content": "string", "background_style": "string?"}},
    {"type": "post_fanpage", "label": "Post na fanpage", "category": "facebook",
     "description": "Opublikuj post na fanpage'u",
     "config_schema": {"fanpage_url": "string", "content": "string"}},
    {"type": "like_page", "label": "Polub stronę", "category": "facebook",
     "description": "Polub stronę na Facebooku",
     "config_schema": {"page_url": "string"}},
    {"type": "comment", "label": "Komentarz", "category": "facebook",
     "description": "Skomentuj post",
     "config_schema": {"post_url": "string", "comment_text": "string"}},
    {"type": "send_message", "label": "Wyślij wiadomość", "category": "facebook",
     "description": "Wyślij wiadomość prywatną",
     "config_schema": {"profile_url": "string", "message_text": "string"}},
    # Flow Control
    {"type": "wait", "label": "Czekaj", "category": "flow",
     "description": "Poczekaj określony czas",
     "config_schema": {"duration": "number", "unit": "string", "random_variation": "boolean?"}},
    {"type": "if_else", "label": "Warunek", "category": "flow",
     "description": "Rozgałęzienie warunkowe (if/else)",
     "config_schema": {"variable": "string", "operator": "string", "value": "string"}},
    {"type": "loop", "label": "Pętla", "category": "flow",
     "description": "Powtórz N razy",
     "config_schema": {"iterations": "number", "iterator_variable": "string?"}},
    {"type": "random_choice", "label": "Losowy wybór", "category": "flow",
     "description": "Losowo wybierz jedną ze ścieżek",
     "config_schema": {"weights": "number[]?"}},
    {"type": "merge", "label": "Złącz", "category": "flow",
     "description": "Poczekaj na wszystkie wejścia",
     "config_schema": {}},
    # Utility
    {"type": "variable", "label": "Zmienna", "category": "utility",
     "description": "Ustaw zmienną kontekstową",
     "config_schema": {"name": "string", "var_type": "string", "value": "string"}},
    {"type": "webhook", "label": "Webhook", "category": "utility",
     "description": "Wyślij HTTP callback",
     "config_schema": {"url": "string", "method": "string?", "body_template": "string?"}},
]


# ── Workflow CRUD ──

@router.get("/workflows/node-types")
async def get_node_types():
    return NODE_TYPES


@router.get("/workflows/", response_model=List[WorkflowListItem])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Workflow).order_by(desc(Workflow.created_at))
    )
    workflows = result.scalars().all()

    items = []
    for wf in workflows:
        # Count nodes in graph_data
        graph = wf.graph_data or {}
        node_count = len(graph.get("nodes", []))

        # Get last run status
        last_run_result = await db.execute(
            select(WorkflowRun.status)
            .where(WorkflowRun.workflow_id == wf.id)
            .order_by(desc(WorkflowRun.created_at))
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

        items.append(WorkflowListItem(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            account_id=wf.account_id,
            status=wf.status,
            node_count=node_count,
            last_run_status=last_run,
            created_at=wf.created_at,
        ))
    return items


@router.post("/workflows/", response_model=WorkflowResponse)
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    wf = Workflow(
        name=data.name,
        description=data.description,
        account_id=data.account_id,
        graph_data=data.graph_data or {
            "nodes": [], "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int, data: WorkflowUpdate, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(wf, key, value)

    await db.commit()
    await db.refresh(wf)
    return wf


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await db.delete(wf)
    await db.commit()
    return {"status": "deleted"}


# ── Workflow Validation ──

@router.post("/workflows/validate")
async def validate_workflow(graph_data: dict):
    """Validate graph for cycles, connectivity, required start/end nodes."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    errors = []

    node_ids = {n["id"] for n in nodes}
    node_types = {n["id"]: n.get("type", "") for n in nodes}

    # Must have exactly one start node
    start_nodes = [n for n in nodes if n.get("type") == "start"]
    if len(start_nodes) == 0:
        errors.append("Brak węzła Start")
    elif len(start_nodes) > 1:
        errors.append("Dozwolony jest tylko jeden węzeł Start")

    # Must have at least one end node
    end_nodes = [n for n in nodes if n.get("type") == "end"]
    if len(end_nodes) == 0:
        errors.append("Brak węzła Koniec")

    # Check edge references
    for edge in edges:
        if edge.get("source") not in node_ids:
            errors.append(f"Krawędź odwołuje się do nieistniejącego źródła: {edge.get('source')}")
        if edge.get("target") not in node_ids:
            errors.append(f"Krawędź odwołuje się do nieistniejącego celu: {edge.get('target')}")

    # Cycle detection (Kahn's algorithm)
    if not errors:
        in_degree = {nid: 0 for nid in node_ids}
        adjacency = {nid: [] for nid in node_ids}
        for edge in edges:
            src, tgt = edge.get("source"), edge.get("target")
            if src in node_ids and tgt in node_ids:
                adjacency[src].append(tgt)
                in_degree[tgt] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(node_ids):
            errors.append("Graf zawiera cykl — workflow musi być acykliczny (DAG)")

    return {"valid": len(errors) == 0, "errors": errors}


# ── Workflow Runs ──

@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
async def start_workflow_run(
    workflow_id: int, data: WorkflowRunCreate = None, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    variables = (data.variables if data else None) or {}

    run = WorkflowRun(
        workflow_id=workflow_id,
        status="PENDING",
        trigger_type="manual",
        variables=variables,
        graph_snapshot=wf.graph_data,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Submit to async task runner
    from app.core.config import settings
    if settings.STANDALONE:
        from app import task_runner
        await task_runner.submit_workflow_task(workflow_id, run.id, variables)
    else:
        from app.worker import run_workflow_task
        run_workflow_task.delay(workflow_id, run.id, variables)

    return run


@router.post("/workflows/{workflow_id}/runs/{run_id}/cancel")
async def cancel_workflow_run(
    workflow_id: int, run_id: int, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.workflow_id == workflow_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=400, detail="Run is not active")

    run.status = "CANCELLED"
    await db.commit()

    # Signal the running asyncio task to stop (interrupts asyncio.sleep).
    from app.core.config import settings
    if settings.STANDALONE:
        from app import task_runner
        await task_runner.cancel_workflow_task(workflow_id, run_id)

    return {"status": "cancelled"}


@router.get("/workflows/{workflow_id}/runs", response_model=List[WorkflowRunResponse])
async def list_workflow_runs(
    workflow_id: int, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(desc(WorkflowRun.created_at))
        .limit(50)
    )
    return result.scalars().all()


@router.get("/workflows/{workflow_id}/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(
    workflow_id: int, run_id: int, db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.workflow_id == workflow_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get(
    "/workflows/{workflow_id}/runs/{run_id}/nodes",
    response_model=List[NodeExecutionResponse],
)
async def get_run_node_executions(
    workflow_id: int, run_id: int, db: AsyncSession = Depends(get_db),
):
    # Verify run belongs to workflow
    run_result = await db.execute(
        select(WorkflowRun.id)
        .where(WorkflowRun.id == run_id, WorkflowRun.workflow_id == workflow_id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(WorkflowNodeExecution)
        .where(WorkflowNodeExecution.run_id == run_id)
        .order_by(WorkflowNodeExecution.started_at)
    )
    return result.scalars().all()
