from strategic_alpha_engine.infrastructure.metadata import load_seed_metadata_catalog


def test_seed_metadata_catalog_loads_expected_entries():
    catalog = load_seed_metadata_catalog()

    assert catalog.get_field("cashflow_op") is not None
    assert catalog.get_field("cashflow_op").update_cadence == "quarterly"
    assert catalog.get_operator("rank") is not None
    assert catalog.get_operator("rank").category == "cross_sectional"


def test_seed_metadata_catalog_filters_fundamental_medium_excerpt():
    catalog = load_seed_metadata_catalog()

    excerpt = catalog.build_field_excerpt(field_classes=["fundamental"], horizons=["medium"], limit=10)

    excerpt_ids = [entry.field_id for entry in excerpt]

    assert "cashflow_op" in excerpt_ids
    assert "debt_lt" in excerpt_ids
    assert "close" not in excerpt_ids
