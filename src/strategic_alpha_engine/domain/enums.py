from enum import Enum


class ResearchFamily(str, Enum):
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    QUALITY_VALUE = "quality_value"
    QUALITY_DETERIORATION = "quality_deterioration"
    LIQUIDITY_STRESS = "liquidity_stress"
    REVISION_DRIFT = "revision_drift"
    VOLATILITY_REGIME = "volatility_regime"
    FLOW_LIQUIDITY = "flow_liquidity"


class ResearchHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ExpectedDirection(str, Enum):
    HIGHER_SIGNAL_OUTPERFORMS = "higher_signal_outperforms"
    LOWER_SIGNAL_OUTPERFORMS = "lower_signal_outperforms"
    NON_MONOTONIC = "non_monotonic"


class FieldClass(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    FUNDAMENTAL = "fundamental"
    ANALYST = "analyst"
    SENTIMENT = "sentiment"
    LIQUIDITY = "liquidity"
    RISK = "risk"
    MACRO = "macro"
    ALTERNATIVE = "alternative"


class UpdateCadence(str, Enum):
    INTRADAY = "intraday"
    DAILY = "daily"
    WEEKLY = "weekly"
    EVENT_DRIVEN = "event_driven"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    IRREGULAR = "irregular"
    SLOW = "slow"


class FieldRole(str, Enum):
    PRIMARY_SIGNAL = "primary_signal"
    SECONDARY_SIGNAL = "secondary_signal"
    DENOMINATOR_SCALE = "denominator_scale"
    CONFIRMATION = "confirmation"
    RISK_CONTROL = "risk_control"
    GATING = "gating"


class TransformKind(str, Enum):
    DELTA = "delta"
    DELAY = "delay"
    RATIO = "ratio"
    SPREAD = "spread"
    RANK = "rank"
    TS_RANK = "ts_rank"
    ZSCORE = "zscore"
    TS_ZSCORE = "ts_zscore"
    VOLATILITY_SCALE = "volatility_scale"
    SMOOTHING = "smoothing"
    DECAY_LINEAR = "decay_linear"
    ROLLING_MEAN = "rolling_mean"
    ROLLING_SUM = "rolling_sum"
    ROLLING_STDDEV = "rolling_stddev"
    LOG = "log"
    SIGNED_POWER = "signed_power"


class NormalizationKind(str, Enum):
    CROSS_SECTIONAL_RANK = "cross_sectional_rank"
    CROSS_SECTIONAL_ZSCORE = "cross_sectional_zscore"
    TIME_SERIES_RANK = "time_series_rank"
    TIME_SERIES_ZSCORE = "time_series_zscore"
    NONE = "none"


class NormalizationTarget(str, Enum):
    SUBSIGNAL = "subsignal"
    FINAL_EXPRESSION = "final_expression"


class RiskControlKind(str, Enum):
    OUTER_RANK = "outer_rank"
    OUTLIER_CONTROL = "outlier_control"
    VOLATILITY_SCALING = "volatility_scaling"
    LIQUIDITY_FILTER = "liquidity_filter"
    TURNOVER_CONTROL = "turnover_control"
    NEUTRALIZATION = "neutralization"
    TRUNCATION = "truncation"
    DENOMINATOR_FLOOR = "denominator_floor"
    LEVERAGE_GUARD = "leverage_guard"


class CandidateGenerationMethod(str, Enum):
    SKELETON_FILL = "skeleton_fill"
    LLM_SYNTHESIS = "llm_synthesis"
    MANUAL = "manual"


class OperatorCategory(str, Enum):
    ARITHMETIC = "arithmetic"
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    CONTROL_FLOW = "control_flow"


class OutlierRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SimulationStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class CandidateLifecycleStage(str, Enum):
    DRAFT = "draft"
    CRITIQUE_PASSED = "critique_passed"
    SIM_PASSED = "sim_passed"
    ROBUST_CANDIDATE = "robust_candidate"
    SUBMISSION_READY = "submission_ready"
    REJECTED = "rejected"


class RunKind(str, Enum):
    PLAN = "plan"
    SYNTHESIZE = "synthesize"
    SIMULATE = "simulate"
    RESEARCH_ONCE = "research_once"
    VALIDATE = "validate"
    PROMOTE = "promote"
    STATUS = "status"
    RESEARCH_LOOP = "research_loop"


class RunLifecycleStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationBacklogStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
