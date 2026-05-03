"""
Init/wiring tests for the Solution Architect, Developer, and QA Reviewer agents.

DDC-specific behavior is tested in test_solution_architect.py,
test_developer.py, and test_qa_reviewer.py.
"""

from __future__ import annotations

from app.agents.developer import Developer
from app.agents.qa_reviewer import QAReviewer
from app.agents.solution_architect import SolutionArchitect
from app.schemas.agent_outputs import CodeOutput, QAReview, TechnicalDesign
from app.schemas.pipeline_events import AgentName


class TestSolutionArchitectInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_solution_architect(self, mock_anthropic):
        agent = SolutionArchitect()
        assert agent.name == AgentName.SOLUTION_ARCHITECT

    def test_output_schema_is_technical_design(self, mock_anthropic):
        agent = SolutionArchitect()
        assert agent.output_schema is TechnicalDesign

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = SolutionArchitect()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_solution_architect(self, mock_anthropic):
        agent = SolutionArchitect()
        assert "Solution Architect" in agent.system_prompt


class TestDeveloperInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_developer(self, mock_anthropic):
        agent = Developer()
        assert agent.name == AgentName.DEVELOPER

    def test_output_schema_is_code_output(self, mock_anthropic):
        agent = Developer()
        assert agent.output_schema is CodeOutput

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = Developer()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_developer(self, mock_anthropic):
        agent = Developer()
        assert "Developer" in agent.system_prompt


class TestQAReviewerInit:
    """__init__() wires the correct name, schema, and non-empty system prompt."""

    def test_agent_name_is_qa_reviewer(self, mock_anthropic):
        agent = QAReviewer()
        assert agent.name == AgentName.QA_REVIEWER

    def test_output_schema_is_qa_review(self, mock_anthropic):
        agent = QAReviewer()
        assert agent.output_schema is QAReview

    def test_system_prompt_is_non_empty(self, mock_anthropic):
        agent = QAReviewer()
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_qa_reviewer(self, mock_anthropic):
        agent = QAReviewer()
        assert "QA Reviewer" in agent.system_prompt
