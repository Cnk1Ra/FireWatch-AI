"""
FireWatch AI - Prediction Module
Fire spread prediction, risk assessment, and evacuation routing.
"""

from src.prediction.propagation_model import (
    PropagationPrediction,
    predict_fire_spread,
    calculate_spread_rate,
)
from src.prediction.spread_calculator import (
    SpreadResult,
    calculate_fire_spread,
    rothermel_spread_rate,
)
from src.prediction.risk_index import (
    FireRiskAssessment,
    calculate_fire_risk,
    get_risk_forecast,
)
from src.prediction.evacuation_router import (
    EvacuationPlan,
    EvacuationRoute,
    calculate_evacuation_routes,
    identify_at_risk_communities,
)

__all__ = [
    # Propagation
    "PropagationPrediction",
    "predict_fire_spread",
    "calculate_spread_rate",
    # Spread Calculator
    "SpreadResult",
    "calculate_fire_spread",
    "rothermel_spread_rate",
    # Risk Index
    "FireRiskAssessment",
    "calculate_fire_risk",
    "get_risk_forecast",
    # Evacuation
    "EvacuationPlan",
    "EvacuationRoute",
    "calculate_evacuation_routes",
    "identify_at_risk_communities",
]
