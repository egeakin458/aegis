"""
Schema validation tests.

Verifies that all Pydantic schemas can be instantiated with example data
and that validation constraints work correctly.
"""

from datetime import datetime, timezone

import pytest

from app.schemas.customer_config import (
    AssumedField,
    BusinessContext,
    BusinessSize,
    ClarificationQuestion,
    ClarificationRound,
    CustomerConfig,
    DataRequirements,
    DesignPreferences,
    DesignStyle,
    FeatureRequest,
    Features,
    FileUpload,
    FinalizedConfig,
    IndustryType,
    MobileSupport,
    ProblemStatement,
    ProjectMeta,
    TechnicalRequirements,
    UserType,
)
from app.schemas.agent_outputs import (
    APIEndpoint,
    CodeFile,
    CodeOutput,
    DataField,
    DataModel,
    FileSpec,
    QAReview,
    ReviewIssue,
    ReviewVerdict,
    TechnicalDesign,
    UIComponent,
)
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
    TokenUsage,
)
from app.schemas.evaluation import (
    BenchmarkTask,
    BetaFeedback,
    ComplexityTier,
    EvaluationResult,
    JudgeScore,
)


# ============================================================
# Fixtures — reusable example data
# ============================================================

@pytest.fixture
def sample_customer_config() -> CustomerConfig:
    return CustomerConfig(
        business_context=BusinessContext(
            name="Cafe Latte",
            industry=IndustryType.FOOD_AND_BEVERAGE,
            description="A small coffee shop chain with 3 locations.",
            size=BusinessSize.SMALL,
        ),
        problem_statement=ProblemStatement(
            problem="We need an online ordering system for pickup orders.",
            users=[UserType.CUSTOMERS, UserType.EMPLOYEES],
            current_process="Phone calls and walk-ins only.",
        ),
        features=Features(
            requested=[
                FeatureRequest(description="Menu display with categories", priority=1),
                FeatureRequest(description="Shopping cart and checkout", priority=2),
                FeatureRequest(description="Order status tracking", priority=3),
            ]
        ),
        data=DataRequirements(entities="Menu items, orders, customers"),
    )


@pytest.fixture
def sample_finalized_config(sample_customer_config: CustomerConfig) -> FinalizedConfig:
    return FinalizedConfig(
        config=sample_customer_config,
        assumptions=[
            AssumedField(
                field_path="technical.auth_required",
                original_value=None,
                assumed_value="true",
                reasoning="Customers need accounts to track orders.",
            ),
        ],
        project_summary="Online ordering system for a 3-location coffee shop.",
        is_complete=True,
    )


@pytest.fixture
def sample_technical_design() -> TechnicalDesign:
    return TechnicalDesign(
        reasoning="Standard CRUD app with order management.",
        project_name="cafe-latte-ordering",
        tech_summary="Next.js frontend, FastAPI backend, SQLite database.",
        data_models=[
            DataModel(
                name="MenuItem",
                description="A menu item available for ordering",
                fields=[
                    DataField(name="id", type="integer", required=True),
                    DataField(name="name", type="string", required=True),
                    DataField(name="price", type="float", required=True),
                    DataField(name="category", type="string", required=True),
                ],
                relationships=["has_many:OrderItem"],
            ),
        ],
        api_endpoints=[
            APIEndpoint(
                method="GET",
                path="/api/menu",
                description="List all menu items",
                response="Array of MenuItem objects",
            ),
        ],
        ui_components=[
            UIComponent(
                name="MenuPage",
                type="page",
                description="Displays the menu grouped by category",
                features=["Category filtering", "Add to cart"],
                data_sources=["/api/menu"],
            ),
        ],
        file_structure=[
            FileSpec(path="src/pages/Menu.jsx", purpose="Menu display page"),
            FileSpec(path="src/api/menu.py", purpose="Menu API endpoints"),
        ],
        dependencies=["react", "fastapi", "sqlite3"],
    )


@pytest.fixture
def sample_code_output() -> CodeOutput:
    return CodeOutput(
        reasoning="Implemented all features from the design.",
        project_name="cafe-latte-ordering",
        files=[
            CodeFile(
                path="src/pages/Menu.jsx",
                content="export default function Menu() { return <div>Menu</div> }",
                language="javascript",
                description="Menu display page component",
            ),
        ],
        setup_instructions="npm install && npm run dev",
        features_implemented=["Menu display", "Shopping cart"],
    )


@pytest.fixture
def sample_qa_review() -> QAReview:
    return QAReview(
        reasoning="Code meets requirements with minor issues.",
        verdict=ReviewVerdict.APPROVE,
        issues=[
            ReviewIssue(
                id="issue-1",
                severity="minor",
                category="code_quality",
                affected_file="src/pages/Menu.jsx",
                description="Missing error handling for API calls.",
                suggestion="Add try/catch around fetch calls.",
            ),
        ],
        requirements_coverage={"Menu display": True, "Shopping cart": True},
        code_quality_score=4,
        summary="Application meets requirements. Minor code quality improvements suggested.",
    )


# ============================================================
# Customer Config Tests
# ============================================================

class TestCustomerConfig:
    def test_full_config(self, sample_customer_config: CustomerConfig):
        assert sample_customer_config.business_context.name == "Cafe Latte"
        assert len(sample_customer_config.features.requested) == 3

    def test_minimal_config(self):
        config = CustomerConfig(
            business_context=BusinessContext(
                name="Test Co",
                industry=IndustryType.OTHER,
                industry_other="Consulting",
                description="A test company.",
                size=BusinessSize.SOLO,
            ),
            problem_statement=ProblemStatement(
                problem="Need a website.",
                users=[UserType.OWNER],
            ),
            features=Features(
                requested=[FeatureRequest(description="Landing page", priority=1)]
            ),
            data=DataRequirements(entities="None"),
        )
        assert config.design.style == DesignStyle.NO_PREFERENCE
        assert config.technical.mobile == MobileSupport.NICE_TO_HAVE
        assert config.meta.submitted_at is not None

    def test_feature_priority_must_be_positive(self):
        with pytest.raises(Exception):
            FeatureRequest(description="Bad feature", priority=0)

    def test_features_must_have_at_least_one(self):
        with pytest.raises(Exception):
            Features(requested=[])

    def test_users_must_have_at_least_one(self):
        with pytest.raises(Exception):
            ProblemStatement(problem="test", users=[])


class TestFinalizedConfig:
    def test_full_finalized(self, sample_finalized_config: FinalizedConfig):
        assert sample_finalized_config.is_complete is True
        assert len(sample_finalized_config.assumptions) == 1
        assert sample_finalized_config.assumptions[0].field_path == "technical.auth_required"

    def test_with_clarification_history(self, sample_customer_config: CustomerConfig):
        config = FinalizedConfig(
            config=sample_customer_config,
            clarification_history=[
                ClarificationRound(
                    round_number=1,
                    questions=[
                        ClarificationQuestion(
                            id="q1",
                            topic="authentication",
                            original_input="Need a website",
                            question="Do customers need to create accounts?",
                            suggestions=["Yes", "No", "Optional"],
                        ),
                    ],
                    answers={"q1": "Yes"},
                ),
            ],
            project_summary="Test project.",
            is_complete=True,
        )
        assert len(config.clarification_history) == 1
        assert config.clarification_history[0].answers["q1"] == "Yes"


# ============================================================
# Agent Output Tests
# ============================================================

class TestTechnicalDesign:
    def test_full_design(self, sample_technical_design: TechnicalDesign):
        assert sample_technical_design.project_name == "cafe-latte-ordering"
        assert len(sample_technical_design.data_models) == 1
        assert len(sample_technical_design.data_models[0].fields) == 4

    def test_must_have_at_least_one_model(self):
        with pytest.raises(Exception):
            TechnicalDesign(
                reasoning="test",
                project_name="test",
                tech_summary="test",
                data_models=[],
                api_endpoints=[APIEndpoint(method="GET", path="/", description="test", response="test")],
                ui_components=[UIComponent(name="X", type="page", description="test")],
                file_structure=[FileSpec(path="x", purpose="test")],
            )


class TestCodeOutput:
    def test_full_output(self, sample_code_output: CodeOutput):
        assert sample_code_output.project_name == "cafe-latte-ordering"
        assert len(sample_code_output.files) == 1

    def test_must_have_at_least_one_file(self):
        with pytest.raises(Exception):
            CodeOutput(
                reasoning="test",
                project_name="test",
                files=[],
                setup_instructions="test",
                features_implemented=["test"],
            )


class TestQAReview:
    def test_full_review(self, sample_qa_review: QAReview):
        assert sample_qa_review.verdict == ReviewVerdict.APPROVE
        assert sample_qa_review.code_quality_score == 4

    def test_score_out_of_range(self):
        with pytest.raises(Exception):
            QAReview(
                reasoning="test",
                verdict=ReviewVerdict.APPROVE,
                requirements_coverage={},
                code_quality_score=6,
                summary="test",
            )

    def test_all_verdicts(self):
        assert ReviewVerdict.APPROVE.value == "approve"
        assert ReviewVerdict.REVISE_CODE.value == "revise_code"
        assert ReviewVerdict.REVISE_DESIGN.value == "revise_design"


# ============================================================
# Pipeline Event Tests
# ============================================================

class TestPipelineEvents:
    def test_create_event(self):
        event = PipelineEvent(
            run_id="run-123",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Pipeline has started.",
        )
        assert event.event_id  # auto-generated
        assert event.timestamp  # auto-generated
        assert event.run_id == "run-123"

    def test_event_with_tokens(self):
        event = PipelineEvent(
            run_id="run-123",
            agent=AgentName.DEVELOPER,
            event_type=EventType.LLM_CALL_COMPLETE,
            message="Developer finished thinking.",
            tokens_used=TokenUsage(input_tokens=1000, output_tokens=500),
            duration_ms=3500,
        )
        assert event.tokens_used.input_tokens == 1000
        assert event.duration_ms == 3500

    def test_to_sse(self):
        event = PipelineEvent(
            run_id="run-123",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Started.",
        )
        sse_data = event.to_sse()
        assert '"run_id":"run-123"' in sse_data
        assert '"event_type":"pipeline_started"' in sse_data

    def test_pipeline_run(self):
        run = PipelineRun()
        assert run.run_id  # auto-generated
        assert run.state == PipelineState.INTAKE
        assert run.total_tokens.input_tokens == 0
        assert run.feedback_cycles == {"code_revisions": 0, "design_revisions": 0}


# ============================================================
# Evaluation Tests
# ============================================================

class TestEvaluation:
    def test_benchmark_task(self):
        task = BenchmarkTask(
            task_id="bench-1",
            name="Simple Portfolio",
            description="A simple portfolio website.",
            complexity=ComplexityTier.SIMPLE,
            customer_config={"business_context": {"name": "Test"}},
            expected_features=["Landing page", "Contact form"],
        )
        assert task.complexity == ComplexityTier.SIMPLE

    def test_judge_score_range(self):
        score = JudgeScore(
            requirements_coverage=5,
            code_organization=4,
            documentation_quality=3,
            overall_coherence=4,
            reasoning="Good overall quality.",
        )
        assert score.requirements_coverage == 5

    def test_judge_score_out_of_range(self):
        with pytest.raises(Exception):
            JudgeScore(
                requirements_coverage=6,
                code_organization=4,
                documentation_quality=3,
                overall_coherence=4,
                reasoning="test",
            )

    def test_evaluation_result(self):
        result = EvaluationResult(
            task_id="bench-1",
            system="aegis",
            judge_scores=[
                JudgeScore(
                    requirements_coverage=4,
                    code_organization=4,
                    documentation_quality=3,
                    overall_coherence=4,
                    reasoning="Run 1",
                ),
                JudgeScore(
                    requirements_coverage=5,
                    code_organization=4,
                    documentation_quality=4,
                    overall_coherence=5,
                    reasoning="Run 2",
                ),
                JudgeScore(
                    requirements_coverage=4,
                    code_organization=3,
                    documentation_quality=4,
                    overall_coherence=4,
                    reasoning="Run 3",
                ),
            ],
        )
        assert len(result.judge_scores) == 3

    def test_beta_feedback(self):
        feedback = BetaFeedback(
            evaluator="student",
            scenario_description="Built a café ordering app.",
            output_match=4,
            quality_rating=4,
            process_clarity=5,
            clarification_helpful=4,
            trust_issues=False,
            would_use_again=True,
        )
        assert feedback.evaluator == "student"
        assert feedback.trust_issues is False


# ============================================================
# Cross-schema consistency tests
# ============================================================

class TestCrossSchemaConsistency:
    """Verify that schemas align with the pipeline data flow."""

    def test_ra_output_feeds_sa_input(self, sample_finalized_config: FinalizedConfig):
        """FinalizedConfig contains a CustomerConfig that SA can read."""
        assert isinstance(sample_finalized_config.config, CustomerConfig)
        assert sample_finalized_config.config.features.requested[0].description

    def test_sa_output_feeds_dev_input(self, sample_technical_design: TechnicalDesign):
        """TechnicalDesign has file_structure that Developer should implement."""
        assert len(sample_technical_design.file_structure) > 0
        assert all(f.path for f in sample_technical_design.file_structure)

    def test_dev_output_feeds_qa_input(self, sample_code_output: CodeOutput):
        """CodeOutput has files that QA can review."""
        assert len(sample_code_output.files) > 0
        assert all(f.content for f in sample_code_output.files)

    def test_pipeline_event_agents_cover_all_pipeline_stages(self):
        """All pipeline agents have an AgentName enum value."""
        expected = {"requirements_analyst", "solution_architect", "developer", "qa_reviewer", "system"}
        actual = {a.value for a in AgentName}
        assert actual == expected

    def test_serialization_roundtrip(self, sample_customer_config: CustomerConfig):
        """Schema can be serialized to JSON and deserialized back."""
        json_str = sample_customer_config.model_dump_json()
        restored = CustomerConfig.model_validate_json(json_str)
        assert restored.business_context.name == sample_customer_config.business_context.name
