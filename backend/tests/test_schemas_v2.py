"""
Tests for DDC v1 schema (CustomerConfigV2).

Covers: happy path, referential integrity errors, uniqueness checks,
default value generation, and schema_version literal.
"""

import json
import pathlib
import pytest
from pydantic import ValidationError

from app.schemas.customer_config import (
    Actor,
    Attribute,
    BusinessRule,
    CustomerConfigV2,
    DomainEntity,
    ProjectContext,
    Relationship,
    UseCase,
)


_FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# --- Golden fixture test ---

def test_golden_fixture_validates():
    """The e-commerce golden fixture must validate cleanly against CustomerConfigV2."""
    raw = json.loads((_FIXTURES_DIR / "ddc_ecommerce.json").read_text())
    cfg = CustomerConfigV2.model_validate(raw)
    assert cfg.schema_version == "ddc-v1"
    assert len(cfg.actors) == 2
    assert len(cfg.entities) == 3
    assert len(cfg.relationships) == 2
    assert len(cfg.business_rules) == 3
    assert len(cfg.use_cases) == 5
    # Verify actor role names
    role_names = {a.role_name for a in cfg.actors}
    assert role_names == {"Customer", "Admin"}
    # Verify entity names
    entity_names = {e.name for e in cfg.entities}
    assert entity_names == {"Product", "Order", "OrderItem"}
    # Verify all use_case actor/entity refs are valid
    actor_ids = {a.id for a in cfg.actors}
    entity_ids = {e.id for e in cfg.entities}
    for uc in cfg.use_cases:
        assert uc.actor_id in actor_ids
        assert uc.primary_entity_id in entity_ids


# --- Helpers ---

def _make_context(**overrides) -> dict:
    base = {
        "name": "my-shop",
        "domain_description": "An online retail store that lets customers browse products and place orders with full checkout flow.",
        "industry": "retail",
    }
    base.update(overrides)
    return base


def _make_actor(role_name="Customer", auth_method="email_password", **overrides) -> dict:
    base = {
        "role_name": role_name,
        "auth_method": auth_method,
        "permissions_description": "Can browse products, add to cart, and place orders.",
    }
    base.update(overrides)
    return base


def _make_entity(name="Product", **overrides) -> dict:
    base = {
        "name": name,
        "attributes": [{"name": "title", "type": "string"}],
    }
    base.update(overrides)
    return base


def _make_use_case(name="Browse Products", uc_type="query", actor_id="", entity_id="", **overrides) -> dict:
    base = {
        "name": name,
        "type": uc_type,
        "actor_id": actor_id,
        "primary_entity_id": entity_id,
    }
    base.update(overrides)
    return base


def _minimal_valid() -> CustomerConfigV2:
    actor = Actor(**_make_actor())
    entity = DomainEntity(**_make_entity())
    uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
    return CustomerConfigV2(
        context=ProjectContext(**_make_context()),
        actors=[actor],
        entities=[entity],
        use_cases=[uc],
    )


# --- Tests ---

class TestCustomerConfigV2:

    def test_happy_path_minimal(self):
        cfg = _minimal_valid()
        assert cfg.schema_version == "ddc-v1"
        assert len(cfg.actors) == 1
        assert len(cfg.entities) == 1
        assert len(cfg.use_cases) == 1

    def test_default_schema_version(self):
        cfg = _minimal_valid()
        assert cfg.schema_version == "ddc-v1"

    def test_default_visual_style(self):
        cfg = _minimal_valid()
        assert cfg.context.visual_style == "clean_minimal"

    def test_default_mobile_first(self):
        cfg = _minimal_valid()
        assert cfg.context.mobile_first is True

    def test_ids_auto_generated(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        assert actor.id.startswith("act_")
        assert entity.id.startswith("ent_")
        assert uc.id.startswith("uc_")

    def test_relationship_id_auto_generated(self):
        actor = Actor(**_make_actor())
        e1 = DomainEntity(**_make_entity("Order"))
        e2 = DomainEntity(**_make_entity("Product"))
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=e1.id))
        rel = Relationship(
            from_entity_id=e1.id,
            to_entity_id=e2.id,
            kind="one_to_many",
            name="order_items",
        )
        cfg = CustomerConfigV2(
            context=ProjectContext(**_make_context()),
            actors=[actor],
            entities=[e1, e2],
            relationships=[rel],
            use_cases=[uc],
        )
        assert cfg.relationships[0].id.startswith("rel_")

    def test_duplicate_actor_role_names_rejected(self):
        actor1 = Actor(**_make_actor("Admin"))
        actor2 = Actor(**_make_actor("Admin"))
        entity = DomainEntity(**_make_entity())
        uc = UseCase(**_make_use_case(actor_id=actor1.id, entity_id=entity.id))
        with pytest.raises(ValidationError, match="role_names must be unique"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor1, actor2],
                entities=[entity],
                use_cases=[uc],
            )

    def test_duplicate_entity_names_rejected(self):
        actor = Actor(**_make_actor())
        e1 = DomainEntity(**_make_entity("Product"))
        e2 = DomainEntity(**_make_entity("Product"))
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=e1.id))
        with pytest.raises(ValidationError, match="Entity names must be unique"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[e1, e2],
                use_cases=[uc],
            )

    def test_use_case_unknown_actor_id(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        uc = UseCase(**_make_use_case(actor_id="act_nonexistent", entity_id=entity.id))
        with pytest.raises(ValidationError, match="unknown actor_id"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_use_case_unknown_entity_id(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id="ent_nonexistent"))
        with pytest.raises(ValidationError, match="unknown primary_entity_id"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_use_case_unknown_business_rule_id(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        uc = UseCase(
            **_make_use_case(actor_id=actor.id, entity_id=entity.id),
            business_rule_ids=["rule_nonexistent"],
        )
        with pytest.raises(ValidationError, match="unknown business_rule_id"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_entity_owned_by_unknown_actor_rejected(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(
            name="Order",
            attributes=[{"name": "total", "type": "decimal"}],
            owned_by_actor_id="act_nonexistent",
        )
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        with pytest.raises(ValidationError, match="owned_by unknown Actor"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_entity_duplicate_attribute_names_rejected(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(
            name="Product",
            attributes=[
                {"name": "title", "type": "string"},
                {"name": "title", "type": "text"},
            ],
        )
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        with pytest.raises(ValidationError, match="duplicate attribute names"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_relationship_unknown_from_entity_rejected(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity("Order"))
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        rel = Relationship(
            from_entity_id="ent_nonexistent",
            to_entity_id=entity.id,
            kind="one_to_many",
            name="order_items",
        )
        with pytest.raises(ValidationError, match="unknown from_entity_id"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                relationships=[rel],
                use_cases=[uc],
            )

    def test_relationship_unknown_to_entity_rejected(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity("Order"))
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        rel = Relationship(
            from_entity_id=entity.id,
            to_entity_id="ent_nonexistent",
            kind="one_to_many",
            name="order_items",
        )
        with pytest.raises(ValidationError, match="unknown to_entity_id"):
            CustomerConfigV2(
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                relationships=[rel],
                use_cases=[uc],
            )

    def test_business_rule_reference_works(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        rule = BusinessRule(
            description="Stock must be positive before confirming order.",
            trigger_condition="When Order state is Pending",
            enforcement_action="Reject if stock < 1, return 422",
        )
        uc = UseCase(
            **_make_use_case(actor_id=actor.id, entity_id=entity.id),
            business_rule_ids=[rule.id],
        )
        cfg = CustomerConfigV2(
            context=ProjectContext(**_make_context()),
            actors=[actor],
            entities=[entity],
            business_rules=[rule],
            use_cases=[uc],
        )
        assert cfg.use_cases[0].business_rule_ids[0] == rule.id

    def test_schema_version_literal_enforced(self):
        actor = Actor(**_make_actor())
        entity = DomainEntity(**_make_entity())
        uc = UseCase(**_make_use_case(actor_id=actor.id, entity_id=entity.id))
        with pytest.raises(ValidationError):
            CustomerConfigV2(
                schema_version="legacy-v1",  # type: ignore
                context=ProjectContext(**_make_context()),
                actors=[actor],
                entities=[entity],
                use_cases=[uc],
            )

    def test_attribute_snake_case_pattern_enforced(self):
        with pytest.raises(ValidationError):
            Attribute(name="MyField", type="string")  # PascalCase rejected

    def test_actor_role_name_pascal_case_enforced(self):
        with pytest.raises(ValidationError):
            Actor(
                role_name="customer",  # lowercase rejected
                auth_method="anonymous",
                permissions_description="Browse only.",
            )

    def test_entity_name_pascal_case_enforced(self):
        with pytest.raises(ValidationError):
            DomainEntity(
                name="product",  # lowercase rejected
                attributes=[{"name": "title", "type": "string"}],
            )

    def test_full_config_with_all_dimensions(self):
        customer = Actor(
            role_name="Customer",
            auth_method="email_password",
            permissions_description="Browse products and place orders on the platform.",
        )
        admin = Actor(
            role_name="Admin",
            auth_method="email_password",
            permissions_description="Manage product catalog and view all orders.",
        )
        product = DomainEntity(
            name="Product",
            attributes=[
                {"name": "title", "type": "string"},
                {"name": "price", "type": "decimal"},
                {"name": "stock", "type": "integer"},
            ],
            states=["Active", "OutOfStock", "Discontinued"],
        )
        order = DomainEntity(
            name="Order",
            attributes=[
                {"name": "total", "type": "decimal"},
                {"name": "state", "type": "string"},
            ],
            states=["Pending", "Confirmed", "Shipped", "Delivered"],
            owned_by_actor_id=customer.id,
        )
        rule = BusinessRule(
            description="Stock must be positive before confirming order.",
            trigger_condition="When Order.state transitions to Confirmed",
            enforcement_action="Reject if Product.stock < 1, return 422",
        )
        rel = Relationship(
            from_entity_id=order.id,
            to_entity_id=product.id,
            kind="many_to_many",
            name="order_items",
        )
        uc_browse = UseCase(
            name="Browse Products",
            type="query",
            actor_id=customer.id,
            primary_entity_id=product.id,
        )
        uc_place_order = UseCase(
            name="Place Order",
            type="command",
            actor_id=customer.id,
            primary_entity_id=order.id,
            business_rule_ids=[rule.id],
        )
        cfg = CustomerConfigV2(
            context=ProjectContext(
                name="my-shop",
                domain_description="An online retail store for electronics with checkout, inventory management, and order tracking.",
                industry="retail",
                visual_style="bold_modern",
                mobile_first=True,
            ),
            actors=[customer, admin],
            entities=[product, order],
            relationships=[rel],
            business_rules=[rule],
            use_cases=[uc_browse, uc_place_order],
        )
        assert len(cfg.actors) == 2
        assert len(cfg.entities) == 2
        assert len(cfg.relationships) == 1
        assert len(cfg.business_rules) == 1
        assert len(cfg.use_cases) == 2
        assert cfg.context.visual_style == "bold_modern"
