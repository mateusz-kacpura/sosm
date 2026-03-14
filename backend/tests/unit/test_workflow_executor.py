import pytest
from collections import defaultdict

from app.workflow.executor import WorkflowExecutor


class TestParseGraph:
    def test_basic_graph(self):
        graph = {
            "nodes": [
                {"id": "n1", "type": "start"},
                {"id": "n2", "type": "end"},
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
            ],
        }
        nodes_map, adjacency, reverse_adj = WorkflowExecutor._parse_graph(graph)

        assert "n1" in nodes_map
        assert "n2" in nodes_map
        assert adjacency["n1"][0][0] == "n2"
        assert reverse_adj["n2"] == ["n1"]

    def test_empty_graph(self):
        nodes_map, adjacency, reverse_adj = WorkflowExecutor._parse_graph(
            {"nodes": [], "edges": []}
        )
        assert nodes_map == {}
        assert adjacency == {}
        assert reverse_adj == {}

    def test_branching_graph(self):
        graph = {
            "nodes": [
                {"id": "start"},
                {"id": "if"},
                {"id": "true_branch"},
                {"id": "false_branch"},
                {"id": "end"},
            ],
            "edges": [
                {"source": "start", "target": "if"},
                {"source": "if", "target": "true_branch", "sourceHandle": "true"},
                {"source": "if", "target": "false_branch", "sourceHandle": "false"},
                {"source": "true_branch", "target": "end"},
                {"source": "false_branch", "target": "end"},
            ],
        }
        nodes_map, adjacency, reverse_adj = WorkflowExecutor._parse_graph(graph)

        assert len(adjacency["if"]) == 2
        assert len(reverse_adj["end"]) == 2

    def test_missing_source_target_skipped(self):
        graph = {
            "nodes": [{"id": "n1"}],
            "edges": [{"source": None, "target": "n1"}],
        }
        nodes_map, adjacency, reverse_adj = WorkflowExecutor._parse_graph(graph)
        assert adjacency == {}


class TestTopologicalSort:
    def test_linear_graph(self):
        nodes_map = {"a": {}, "b": {}, "c": {}}
        adjacency = {
            "a": [("b", {})],
            "b": [("c", {})],
        }
        result = WorkflowExecutor._topological_sort(nodes_map, adjacency)
        assert result == ["a", "b", "c"]

    def test_diamond_graph(self):
        nodes_map = {"a": {}, "b": {}, "c": {}, "d": {}}
        adjacency = {
            "a": [("b", {}), ("c", {})],
            "b": [("d", {})],
            "c": [("d", {})],
        }
        result = WorkflowExecutor._topological_sort(nodes_map, adjacency)
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_single_node(self):
        result = WorkflowExecutor._topological_sort({"a": {}}, {})
        assert result == ["a"]

    def test_cycle_raises(self):
        nodes_map = {"a": {}, "b": {}, "c": {}}
        adjacency = {
            "a": [("b", {})],
            "b": [("c", {})],
            "c": [("a", {})],
        }
        with pytest.raises(ValueError, match="cykl"):
            WorkflowExecutor._topological_sort(nodes_map, adjacency)

    def test_self_loop_raises(self):
        nodes_map = {"a": {}}
        adjacency = {"a": [("a", {})]}
        with pytest.raises(ValueError, match="cykl"):
            WorkflowExecutor._topological_sort(nodes_map, adjacency)

    def test_disconnected_graph(self):
        nodes_map = {"a": {}, "b": {}, "c": {}, "d": {}}
        adjacency = {
            "a": [("b", {})],
            "c": [("d", {})],
        }
        result = WorkflowExecutor._topological_sort(nodes_map, adjacency)
        assert len(result) == 4
        assert result.index("a") < result.index("b")
        assert result.index("c") < result.index("d")

    def test_complex_dag(self):
        """
        start -> login -> if_else -> [true: post_group -> end]
                                     [false: wait -> end]
        """
        nodes_map = {
            "start": {}, "login": {}, "if_else": {},
            "post_group": {}, "wait": {}, "end": {},
        }
        adjacency = {
            "start": [("login", {})],
            "login": [("if_else", {})],
            "if_else": [("post_group", {"sourceHandle": "true"}), ("wait", {"sourceHandle": "false"})],
            "post_group": [("end", {})],
            "wait": [("end", {})],
        }
        result = WorkflowExecutor._topological_sort(nodes_map, adjacency)
        assert len(result) == 6
        assert result[0] == "start"
        assert result[-1] == "end"
        assert result.index("login") < result.index("if_else")


class TestMarkSubtreeSkipped:
    def test_marks_simple_subtree(self):
        executor = WorkflowExecutor()
        adjacency = {
            "a": [("b", {}), ("c", {})],
            "b": [("d", {})],
        }
        skipped = set()
        completed = set()
        executor._mark_subtree_skipped("a", adjacency, skipped, completed)
        assert skipped == {"a", "b", "c", "d"}

    def test_does_not_skip_completed(self):
        executor = WorkflowExecutor()
        adjacency = {
            "a": [("b", {})],
            "b": [("c", {})],
        }
        skipped = set()
        completed = {"b"}
        executor._mark_subtree_skipped("a", adjacency, skipped, completed)
        assert skipped == {"a"}
        assert "b" not in skipped

    def test_does_not_duplicate_skip(self):
        executor = WorkflowExecutor()
        adjacency = {
            "a": [("b", {}), ("c", {})],
            "b": [("c", {})],
        }
        skipped = set()
        executor._mark_subtree_skipped("a", adjacency, skipped, set())
        assert skipped == {"a", "b", "c"}
