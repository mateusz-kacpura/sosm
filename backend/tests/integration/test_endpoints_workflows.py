import pytest


SIMPLE_GRAPH = {
    "nodes": [
        {"id": "n1", "type": "start", "position": {"x": 0, "y": 0}, "data": {"label": "Start", "config": {}}},
        {"id": "n2", "type": "end", "position": {"x": 300, "y": 0}, "data": {"label": "Koniec", "config": {}}},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


class TestWorkflowCRUD:
    async def test_create_workflow(self, client):
        response = await client.post(
            "/api/workflows/",
            json={"name": "Test Workflow", "description": "A test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert data["description"] == "A test"
        assert data["status"] == "SZKIC"
        assert "id" in data
        assert data["graph_data"]["nodes"] == []

    async def test_create_workflow_with_graph(self, client):
        response = await client.post(
            "/api/workflows/",
            json={"name": "With Graph", "graph_data": SIMPLE_GRAPH},
        )
        data = response.json()
        assert len(data["graph_data"]["nodes"]) == 2
        assert len(data["graph_data"]["edges"]) == 1

    async def test_create_workflow_minimal(self, client):
        response = await client.post(
            "/api/workflows/",
            json={"name": "Minimal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] is None
        assert data["description"] is None

    async def test_create_workflow_missing_name(self, client):
        response = await client.post(
            "/api/workflows/",
            json={"description": "No name"},
        )
        assert response.status_code == 422

    async def test_list_workflows_empty(self, client):
        response = await client.get("/api/workflows/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_workflows_returns_all(self, client):
        for i in range(3):
            await client.post("/api/workflows/", json={"name": f"WF {i}"})
        response = await client.get("/api/workflows/")
        assert len(response.json()) == 3

    async def test_list_workflows_includes_node_count(self, client):
        await client.post(
            "/api/workflows/",
            json={"name": "With nodes", "graph_data": SIMPLE_GRAPH},
        )
        response = await client.get("/api/workflows/")
        data = response.json()
        assert data[0]["node_count"] == 2

    async def test_get_workflow(self, client):
        create_resp = await client.post(
            "/api/workflows/", json={"name": "Get Me"},
        )
        wf_id = create_resp.json()["id"]
        response = await client.get(f"/api/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Me"

    async def test_get_workflow_not_found(self, client):
        response = await client.get("/api/workflows/99999")
        assert response.status_code == 404

    async def test_update_workflow(self, client):
        create_resp = await client.post(
            "/api/workflows/", json={"name": "Original"},
        )
        wf_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/workflows/{wf_id}",
            json={"name": "Updated", "status": "AKTYWNY"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["status"] == "AKTYWNY"

    async def test_update_workflow_graph(self, client):
        create_resp = await client.post(
            "/api/workflows/", json={"name": "Graph Update"},
        )
        wf_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/workflows/{wf_id}",
            json={"graph_data": SIMPLE_GRAPH},
        )
        assert len(response.json()["graph_data"]["nodes"]) == 2

    async def test_update_workflow_partial(self, client):
        create_resp = await client.post(
            "/api/workflows/", json={"name": "Partial", "description": "Keep me"},
        )
        wf_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/workflows/{wf_id}",
            json={"name": "Changed"},
        )
        data = response.json()
        assert data["name"] == "Changed"
        assert data["description"] == "Keep me"

    async def test_update_workflow_not_found(self, client):
        response = await client.patch(
            "/api/workflows/99999",
            json={"name": "Nope"},
        )
        assert response.status_code == 404

    async def test_delete_workflow(self, client):
        create_resp = await client.post(
            "/api/workflows/", json={"name": "Delete Me"},
        )
        wf_id = create_resp.json()["id"]
        response = await client.delete(f"/api/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify gone
        response = await client.get(f"/api/workflows/{wf_id}")
        assert response.status_code == 404

    async def test_delete_workflow_not_found(self, client):
        response = await client.delete("/api/workflows/99999")
        assert response.status_code == 404


class TestWorkflowValidation:
    async def test_valid_graph(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json=SIMPLE_GRAPH,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []

    async def test_missing_start_node(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={
                "nodes": [{"id": "n1", "type": "end"}],
                "edges": [],
            },
        )
        data = response.json()
        assert data["valid"] is False
        assert any("Start" in e for e in data["errors"])

    async def test_missing_end_node(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={
                "nodes": [{"id": "n1", "type": "start"}],
                "edges": [],
            },
        )
        data = response.json()
        assert data["valid"] is False
        assert any("Koniec" in e for e in data["errors"])

    async def test_multiple_start_nodes(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={
                "nodes": [
                    {"id": "n1", "type": "start"},
                    {"id": "n2", "type": "start"},
                    {"id": "n3", "type": "end"},
                ],
                "edges": [],
            },
        )
        data = response.json()
        assert data["valid"] is False
        assert any("jeden" in e for e in data["errors"])

    async def test_cycle_detected(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={
                "nodes": [
                    {"id": "n1", "type": "start"},
                    {"id": "n2", "type": "wait"},
                    {"id": "n3", "type": "end"},
                ],
                "edges": [
                    {"source": "n1", "target": "n2"},
                    {"source": "n2", "target": "n3"},
                    {"source": "n3", "target": "n2"},
                ],
            },
        )
        data = response.json()
        assert data["valid"] is False
        assert any("cykl" in e for e in data["errors"])

    async def test_invalid_edge_reference(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={
                "nodes": [
                    {"id": "n1", "type": "start"},
                    {"id": "n2", "type": "end"},
                ],
                "edges": [
                    {"source": "n1", "target": "n999"},
                ],
            },
        )
        data = response.json()
        assert data["valid"] is False
        assert any("nieistniejącego" in e for e in data["errors"])

    async def test_empty_graph_invalid(self, client):
        response = await client.post(
            "/api/workflows/validate",
            json={"nodes": [], "edges": []},
        )
        data = response.json()
        assert data["valid"] is False


class TestNodeTypes:
    async def test_get_node_types(self, client):
        response = await client.get("/api/workflows/node-types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        types = {n["type"] for n in data}
        assert "start" in types
        assert "end" in types
        assert "login" in types
        assert "post_group" in types
        assert "wait" in types
        assert "if_else" in types
        assert "variable" in types
        assert "webhook" in types

    async def test_node_types_have_required_fields(self, client):
        response = await client.get("/api/workflows/node-types")
        for node_def in response.json():
            assert "type" in node_def
            assert "label" in node_def
            assert "category" in node_def
            assert "description" in node_def


class TestWorkflowRuns:
    async def test_start_run(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Runnable", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(f"/api/workflows/{wf_id}/run")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["trigger_type"] == "manual"
        assert data["workflow_id"] == wf_id

    async def test_start_run_with_variables(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "With Vars", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/workflows/{wf_id}/run",
            json={"variables": {"key": "value"}},
        )
        data = response.json()
        assert data["variables"] == {"key": "value"}

    async def test_start_run_workflow_not_found(self, client):
        response = await client.post("/api/workflows/99999/run")
        assert response.status_code == 404

    async def test_list_runs(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Multi Run", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        await client.post(f"/api/workflows/{wf_id}/run")
        await client.post(f"/api/workflows/{wf_id}/run")

        response = await client.get(f"/api/workflows/{wf_id}/runs")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_get_run(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Get Run", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/workflows/{wf_id}/run")
        run_id = run_resp.json()["id"]

        response = await client.get(f"/api/workflows/{wf_id}/runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["id"] == run_id

    async def test_get_run_not_found(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "No Run", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        response = await client.get(f"/api/workflows/{wf_id}/runs/99999")
        assert response.status_code == 404

    async def test_cancel_run(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Cancel Me", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/workflows/{wf_id}/run")
        run_id = run_resp.json()["id"]

        response = await client.post(f"/api/workflows/{wf_id}/runs/{run_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

        # Verify status changed
        get_resp = await client.get(f"/api/workflows/{wf_id}/runs/{run_id}")
        assert get_resp.json()["status"] == "CANCELLED"

    async def test_cancel_completed_run_fails(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Done Run", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/workflows/{wf_id}/run")
        run_id = run_resp.json()["id"]

        # Cancel first
        await client.post(f"/api/workflows/{wf_id}/runs/{run_id}/cancel")

        # Cancel again should fail (not active)
        response = await client.post(f"/api/workflows/{wf_id}/runs/{run_id}/cancel")
        assert response.status_code == 400

    async def test_cancel_run_not_found(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "No Cancel", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(f"/api/workflows/{wf_id}/runs/99999/cancel")
        assert response.status_code == 404

    async def test_get_run_node_executions_empty(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Nodes Run", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/workflows/{wf_id}/run")
        run_id = run_resp.json()["id"]

        response = await client.get(f"/api/workflows/{wf_id}/runs/{run_id}/nodes")
        assert response.status_code == 200
        assert response.json() == []

    async def test_run_stores_graph_snapshot(self, client):
        create_resp = await client.post(
            "/api/workflows/",
            json={"name": "Snapshot", "graph_data": SIMPLE_GRAPH},
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(f"/api/workflows/{wf_id}/run")
        run_id = run_resp.json()["id"]

        # Update the workflow graph after run was created
        await client.patch(
            f"/api/workflows/{wf_id}",
            json={"graph_data": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}},
        )

        # The run should still have the original graph (checked via DB later)
        # Here we just verify the run was created successfully
        get_resp = await client.get(f"/api/workflows/{wf_id}/runs/{run_id}")
        assert get_resp.status_code == 200
