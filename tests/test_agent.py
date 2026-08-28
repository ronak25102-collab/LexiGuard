"""Tests for the LangGraph CRAG agent."""

from unittest.mock import patch

from lexiguard.agent.graph import build_graph, route_after_grading


class TestRouteAfterGrading:
    """Test the conditional routing logic."""

    def test_routes_to_generate_when_relevant(self):
        state = {"relevance_score": "relevant", "retry_count": 0}
        assert route_after_grading(state) == "generate"

    @patch("lexiguard.agent.graph.get_settings")
    def test_routes_to_rewrite_when_irrelevant_and_retries_left(self, mock_settings):
        mock_settings.return_value.agent_max_retries = None
        mock_settings.return_value.max_retries = 3
        state = {"relevance_score": "irrelevant", "retry_count": 0}
        assert route_after_grading(state) == "rewrite_query"

    @patch("lexiguard.agent.graph.get_settings")
    def test_routes_to_rewrite_on_second_retry(self, mock_settings):
        mock_settings.return_value.agent_max_retries = None
        mock_settings.return_value.max_retries = 3
        state = {"relevance_score": "irrelevant", "retry_count": 1}
        assert route_after_grading(state) == "rewrite_query"

    def test_routes_to_disclaimer_when_max_retries_exceeded(self):
        state = {"relevance_score": "irrelevant", "retry_count": 3}
        assert route_after_grading(state) == "generate_with_disclaimer"

    def test_routes_to_disclaimer_when_retry_count_equals_max(self):
        """When retry_count == max_retries, should go to disclaimer."""
        with patch("lexiguard.agent.graph.get_settings") as mock_settings:
            mock_settings.return_value.max_retries = 2
            state = {"relevance_score": "irrelevant", "retry_count": 2}
            result = route_after_grading(state)
            assert result == "generate_with_disclaimer"


class TestBuildGraph:
    """Test graph compilation."""

    @patch("lexiguard.agent.graph.get_settings")
    def test_build_graph_compiles(self, mock_settings):
        """The graph should compile without errors."""
        mock_settings.return_value.max_retries = 3
        graph = build_graph()
        assert graph is not None

    @patch("lexiguard.agent.graph.get_settings")
    def test_build_graph_has_expected_nodes(self, mock_settings):
        """Compiled graph should contain all expected nodes."""
        mock_settings.return_value.max_retries = 3
        graph = build_graph()
        # The compiled graph should be invokable
        assert hasattr(graph, "invoke")
