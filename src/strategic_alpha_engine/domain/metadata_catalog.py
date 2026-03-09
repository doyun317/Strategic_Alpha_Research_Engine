from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from strategic_alpha_engine.domain.base import EngineModel
from strategic_alpha_engine.domain.common import (
    FIELD_IDENTIFIER_PATTERN,
    ensure_unique_lower_text,
    ensure_unique_sequence,
)
from strategic_alpha_engine.domain.enums import (
    FieldClass,
    OperatorCategory,
    OutlierRiskLevel,
    ResearchHorizon,
    UpdateCadence,
)


class FieldCatalogEntry(EngineModel):
    field_id: str = Field(pattern=FIELD_IDENTIFIER_PATTERN)
    field_class: FieldClass
    update_cadence: UpdateCadence
    description: str = Field(min_length=8, max_length=240)
    recommended_horizons: list[ResearchHorizon] = Field(default_factory=list, max_length=4)
    discouraged_patterns: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("recommended_horizons")
    @classmethod
    def validate_recommended_horizons(cls, value: list[ResearchHorizon]) -> list[ResearchHorizon]:
        return ensure_unique_sequence(value, "recommended_horizons")

    @field_validator("discouraged_patterns")
    @classmethod
    def validate_discouraged_patterns(cls, value: list[str]) -> list[str]:
        return ensure_unique_lower_text(value, "discouraged_patterns")


class FieldMetadata(FieldCatalogEntry):
    safe_min_lookback_days: int | None = Field(default=None, ge=1, le=2520)
    safe_max_lookback_days: int | None = Field(default=None, ge=1, le=2520)
    normalization_recommendation: str | None = Field(default=None, max_length=120)
    outlier_risk: OutlierRiskLevel = OutlierRiskLevel.MEDIUM

    @model_validator(mode="after")
    def validate_lookback_range(self) -> "FieldMetadata":
        if self.safe_min_lookback_days and self.safe_max_lookback_days:
            if self.safe_min_lookback_days > self.safe_max_lookback_days:
                raise ValueError("safe_min_lookback_days must not exceed safe_max_lookback_days")
        return self

    def to_catalog_entry(self) -> FieldCatalogEntry:
        return FieldCatalogEntry(
            field_id=self.field_id,
            field_class=self.field_class,
            update_cadence=self.update_cadence,
            description=self.description,
            recommended_horizons=self.recommended_horizons,
            discouraged_patterns=self.discouraged_patterns,
        )


class OperatorMetadata(EngineModel):
    operator_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    category: OperatorCategory
    min_arity: int = Field(ge=1, le=8)
    max_arity: int = Field(ge=1, le=8)
    requires_lookback: bool = False
    supports_constants: bool = False
    discouraged_for_cadences: list[UpdateCadence] = Field(default_factory=list, max_length=8)
    notes: str = Field(min_length=8, max_length=240)

    @field_validator("discouraged_for_cadences")
    @classmethod
    def validate_discouraged_for_cadences(
        cls,
        value: list[UpdateCadence],
    ) -> list[UpdateCadence]:
        return ensure_unique_sequence(value, "discouraged_for_cadences")

    @model_validator(mode="after")
    def validate_arity_range(self) -> "OperatorMetadata":
        if self.min_arity > self.max_arity:
            raise ValueError("min_arity must not exceed max_arity")
        return self


class MetadataCatalog(EngineModel):
    fields: list[FieldMetadata] = Field(default_factory=list, max_length=1024)
    operators: list[OperatorMetadata] = Field(default_factory=list, max_length=1024)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "MetadataCatalog":
        field_ids = [field.field_id for field in self.fields]
        operator_ids = [operator.operator_id for operator in self.operators]
        ensure_unique_sequence(field_ids, "fields.field_id")
        ensure_unique_sequence(operator_ids, "operators.operator_id")
        return self

    def get_field(self, field_id: str) -> FieldMetadata | None:
        for field in self.fields:
            if field.field_id == field_id:
                return field
        return None

    def get_operator(self, operator_id: str) -> OperatorMetadata | None:
        for operator in self.operators:
            if operator.operator_id == operator_id:
                return operator
        return None

    def build_field_excerpt(
        self,
        field_classes: list[FieldClass | str] | None = None,
        horizons: list[ResearchHorizon | str] | None = None,
        limit: int = 24,
    ) -> list[FieldCatalogEntry]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        normalized_field_classes = {self._normalize_enum_like(value) for value in field_classes or []}
        normalized_horizons = {self._normalize_enum_like(value) for value in horizons or []}

        excerpt: list[FieldCatalogEntry] = []
        for field in self.fields:
            if normalized_field_classes and self._normalize_enum_like(field.field_class) not in normalized_field_classes:
                continue
            if normalized_horizons and not normalized_horizons.intersection(
                {self._normalize_enum_like(horizon) for horizon in field.recommended_horizons}
            ):
                continue
            excerpt.append(field.to_catalog_entry())
            if len(excerpt) >= limit:
                break
        return excerpt

    @staticmethod
    def _normalize_enum_like(value: FieldClass | ResearchHorizon | str) -> str:
        return value.value if hasattr(value, "value") else str(value)
