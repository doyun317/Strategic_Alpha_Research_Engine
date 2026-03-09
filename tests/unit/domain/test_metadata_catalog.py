import pytest
from pydantic import ValidationError

from strategic_alpha_engine.domain.enums import FieldClass, OperatorCategory, ResearchHorizon, UpdateCadence
from strategic_alpha_engine.domain.metadata_catalog import FieldMetadata, MetadataCatalog, OperatorMetadata


def test_metadata_catalog_rejects_duplicate_field_ids():
    field = FieldMetadata(
        field_id="close",
        field_class=FieldClass.PRICE,
        update_cadence=UpdateCadence.DAILY,
        description="Adjusted close price for liquid equities.",
        recommended_horizons=[ResearchHorizon.SHORT],
        discouraged_patterns=[],
    )

    with pytest.raises(ValidationError):
        MetadataCatalog(fields=[field, field], operators=[])


def test_build_field_excerpt_filters_by_class_and_horizon():
    catalog = MetadataCatalog(
        fields=[
            FieldMetadata(
                field_id="close",
                field_class=FieldClass.PRICE,
                update_cadence=UpdateCadence.DAILY,
                description="Adjusted close price for liquid equities.",
                recommended_horizons=[ResearchHorizon.SHORT, ResearchHorizon.MEDIUM],
                discouraged_patterns=[],
            ),
            FieldMetadata(
                field_id="cashflow_op",
                field_class=FieldClass.FUNDAMENTAL,
                update_cadence=UpdateCadence.QUARTERLY,
                description="Operating cashflow for quality research.",
                recommended_horizons=[ResearchHorizon.MEDIUM],
                discouraged_patterns=["short_delay_on_slow_fundamentals"],
            ),
        ],
        operators=[],
    )

    excerpt = catalog.build_field_excerpt(
        field_classes=[FieldClass.FUNDAMENTAL],
        horizons=[ResearchHorizon.MEDIUM],
    )

    assert [entry.field_id for entry in excerpt] == ["cashflow_op"]


def test_operator_metadata_rejects_inverted_arity():
    with pytest.raises(ValidationError):
        OperatorMetadata(
            operator_id="divide",
            category=OperatorCategory.ARITHMETIC,
            min_arity=2,
            max_arity=1,
            notes="Invalid arity range for testing.",
        )
