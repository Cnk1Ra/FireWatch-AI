"""
FireWatch AI - Fire Spread Calculator
Implements Rothermel fire spread equations.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import math


@dataclass
class FuelModel:
    """Fuel model parameters for fire spread calculation."""
    name: str
    fuel_load_kg_m2: float          # Total fuel load
    fuel_depth_m: float             # Fuel bed depth
    dead_fuel_moisture: float       # Dead fuel moisture content (fraction)
    live_fuel_moisture: float       # Live fuel moisture content (fraction)
    surface_to_volume_ratio: float  # Surface area to volume ratio (1/m)
    heat_content_kj_kg: float       # Heat content of fuel
    mineral_content: float          # Total mineral content (fraction)
    moisture_extinction: float      # Moisture of extinction (fraction)

    @classmethod
    def from_fuel_type(cls, fuel_type: str) -> "FuelModel":
        """Create fuel model from predefined type."""
        models = {
            "floresta_densa": cls(
                name="Dense Forest",
                fuel_load_kg_m2=2.5,
                fuel_depth_m=0.5,
                dead_fuel_moisture=0.15,
                live_fuel_moisture=1.0,
                surface_to_volume_ratio=5000,
                heat_content_kj_kg=18000,
                mineral_content=0.055,
                moisture_extinction=0.30,
            ),
            "cerrado": cls(
                name="Cerrado Savanna",
                fuel_load_kg_m2=0.8,
                fuel_depth_m=0.6,
                dead_fuel_moisture=0.10,
                live_fuel_moisture=0.8,
                surface_to_volume_ratio=6000,
                heat_content_kj_kg=18500,
                mineral_content=0.05,
                moisture_extinction=0.25,
            ),
            "campo": cls(
                name="Grassland",
                fuel_load_kg_m2=0.4,
                fuel_depth_m=0.8,
                dead_fuel_moisture=0.08,
                live_fuel_moisture=0.5,
                surface_to_volume_ratio=8000,
                heat_content_kj_kg=18000,
                mineral_content=0.04,
                moisture_extinction=0.20,
            ),
            "pastagem": cls(
                name="Pasture",
                fuel_load_kg_m2=0.3,
                fuel_depth_m=0.4,
                dead_fuel_moisture=0.10,
                live_fuel_moisture=0.6,
                surface_to_volume_ratio=7000,
                heat_content_kj_kg=17500,
                mineral_content=0.05,
                moisture_extinction=0.22,
            ),
        }
        return models.get(fuel_type, models["cerrado"])


@dataclass
class SpreadResult:
    """Fire spread calculation result."""
    spread_rate_m_per_min: float
    spread_rate_km_per_hour: float
    flame_length_m: float
    fireline_intensity_kw_m: float
    heat_per_unit_area_kj_m2: float
    reaction_intensity_kw_m2: float

    # Direction components
    head_spread_rate: float  # Downwind (fastest)
    flank_spread_rate: float  # Crosswind
    back_spread_rate: float   # Upwind (slowest)

    # Factors
    wind_factor: float
    slope_factor: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spread_rate": {
                "m_per_min": round(self.spread_rate_m_per_min, 2),
                "km_per_hour": round(self.spread_rate_km_per_hour, 3),
            },
            "flame_length_m": round(self.flame_length_m, 2),
            "fireline_intensity_kw_m": round(self.fireline_intensity_kw_m, 1),
            "heat_per_unit_area_kj_m2": round(self.heat_per_unit_area_kj_m2, 1),
            "directional_spread": {
                "head_m_per_min": round(self.head_spread_rate, 2),
                "flank_m_per_min": round(self.flank_spread_rate, 2),
                "back_m_per_min": round(self.back_spread_rate, 2),
            },
            "factors": {
                "wind": round(self.wind_factor, 3),
                "slope": round(self.slope_factor, 3),
            },
        }


def rothermel_spread_rate(
    fuel_model: FuelModel,
    wind_speed_ms: float,
    wind_direction_degrees: float,
    slope_degrees: float,
    slope_aspect_degrees: float = 0
) -> SpreadResult:
    """
    Calculate fire spread rate using Rothermel model.

    This is a simplified implementation of the Rothermel fire spread model,
    which is the standard model used by fire management agencies worldwide.

    Args:
        fuel_model: Fuel model with vegetation parameters
        wind_speed_ms: Mid-flame wind speed in m/s
        wind_direction_degrees: Wind direction (0=N, 90=E)
        slope_degrees: Terrain slope
        slope_aspect_degrees: Direction slope faces (0=N)

    Returns:
        SpreadResult with spread rates and fire characteristics
    """
    # Convert fuel parameters
    w0 = fuel_model.fuel_load_kg_m2 * 0.2048  # kg/m2 to lb/ft2
    delta = fuel_model.fuel_depth_m * 3.281   # m to ft
    sigma = fuel_model.surface_to_volume_ratio * 0.3048  # 1/m to 1/ft
    h = fuel_model.heat_content_kj_kg * 0.4299  # kJ/kg to BTU/lb
    Mf = fuel_model.dead_fuel_moisture
    Mx = fuel_model.moisture_extinction
    Se = fuel_model.mineral_content
    St = 0.01  # Effective mineral content

    # Calculate bulk density (lb/ft3)
    rho_b = w0 / delta if delta > 0 else 0.01

    # Particle density (lb/ft3) - typical value for wood
    rho_p = 32.0

    # Packing ratio
    beta = rho_b / rho_p

    # Optimal packing ratio
    beta_op = 3.348 * (sigma ** -0.8189)

    # Relative packing ratio
    beta_ratio = beta / beta_op if beta_op > 0 else 1.0

    # Maximum reaction velocity (1/min)
    gamma_max = (sigma ** 1.5) / (495 + 0.0594 * (sigma ** 1.5))

    # Optimum reaction velocity
    A = 133 * (sigma ** -0.7913)
    gamma = gamma_max * ((beta_ratio ** A) * math.exp(A * (1 - beta_ratio)))

    # Moisture damping coefficient
    rM = min(Mf / Mx, 1.0) if Mx > 0 else 0
    eta_M = 1 - 2.59 * rM + 5.11 * (rM ** 2) - 3.52 * (rM ** 3)
    eta_M = max(0, eta_M)

    # Mineral damping coefficient
    eta_S = 0.174 * (Se ** -0.19) if Se > 0 else 1.0
    eta_S = max(0, min(1, eta_S))

    # Reaction intensity (BTU/ft2/min)
    I_R = gamma * w0 * h * eta_M * eta_S

    # Propagating flux ratio
    xi = math.exp((0.792 + 0.681 * math.sqrt(sigma)) * (beta + 0.1)) / (192 + 0.2595 * sigma)

    # Effective heating number
    epsilon = math.exp(-138 / sigma) if sigma > 0 else 0

    # Heat of pre-ignition (BTU/lb)
    Q_ig = 250 + 1116 * Mf

    # No-wind, no-slope rate of spread (ft/min)
    R0 = (I_R * xi) / (rho_b * epsilon * Q_ig) if (rho_b * epsilon * Q_ig) > 0 else 0

    # Wind factor
    C = 7.47 * math.exp(-0.133 * (sigma ** 0.55))
    B = 0.02526 * (sigma ** 0.54)
    E = 0.715 * math.exp(-3.59e-4 * sigma)

    U = wind_speed_ms * 196.85  # m/s to ft/min
    phi_w = C * (U ** B) * (beta_ratio ** (-E)) if U > 0 else 0

    # Slope factor
    slope_rad = math.radians(slope_degrees)
    phi_s = 5.275 * (beta ** -0.3) * (math.tan(slope_rad) ** 2)

    # Combined spread rate (ft/min)
    R = R0 * (1 + phi_w + phi_s)

    # Convert to m/min
    spread_rate_m_min = R * 0.3048

    # Calculate directional spread rates
    # Head fire (downwind) gets full wind effect
    head_rate = spread_rate_m_min

    # Back fire (upwind) - minimal spread
    back_rate = R0 * 0.3048 * 0.3  # About 30% of no-wind rate

    # Flank fire (crosswind) - intermediate
    flank_rate = (head_rate + back_rate) / 2 * 0.7

    # Fireline intensity (BTU/ft/s -> kW/m)
    I_B = I_R * R / 60  # BTU/ft/s
    fireline_intensity = I_B * 3.461  # Convert to kW/m

    # Flame length (m) - Byram's equation
    flame_length = 0.0775 * (fireline_intensity ** 0.46)

    # Heat per unit area (kJ/m2)
    heat_per_area = I_R * 11.356 / (R / 60) if R > 0 else 0

    return SpreadResult(
        spread_rate_m_per_min=spread_rate_m_min,
        spread_rate_km_per_hour=spread_rate_m_min * 0.06,
        flame_length_m=flame_length,
        fireline_intensity_kw_m=fireline_intensity,
        heat_per_unit_area_kj_m2=heat_per_area,
        reaction_intensity_kw_m2=I_R * 11.356,
        head_spread_rate=head_rate,
        flank_spread_rate=flank_rate,
        back_spread_rate=back_rate,
        wind_factor=phi_w,
        slope_factor=phi_s,
    )


def calculate_fire_spread(
    wind_speed_kmh: float,
    wind_direction_degrees: float,
    humidity_percent: float,
    temperature_celsius: float,
    slope_degrees: float = 0,
    fuel_type: str = "cerrado"
) -> SpreadResult:
    """
    Simplified fire spread calculation.

    Args:
        wind_speed_kmh: Wind speed in km/h
        wind_direction_degrees: Wind direction
        humidity_percent: Relative humidity
        temperature_celsius: Air temperature
        slope_degrees: Terrain slope
        fuel_type: Vegetation type

    Returns:
        SpreadResult object
    """
    # Get fuel model
    fuel_model = FuelModel.from_fuel_type(fuel_type)

    # Adjust dead fuel moisture based on humidity and temperature
    # Simple empirical adjustment
    base_moisture = fuel_model.dead_fuel_moisture
    humidity_factor = humidity_percent / 50  # 1.0 at 50% RH
    temp_factor = (30 - temperature_celsius) / 30  # Lower at high temps

    adjusted_moisture = base_moisture * humidity_factor * (1 + temp_factor * 0.2)
    adjusted_moisture = max(0.03, min(adjusted_moisture, 0.30))

    # Create adjusted fuel model
    adjusted_fuel = FuelModel(
        name=fuel_model.name,
        fuel_load_kg_m2=fuel_model.fuel_load_kg_m2,
        fuel_depth_m=fuel_model.fuel_depth_m,
        dead_fuel_moisture=adjusted_moisture,
        live_fuel_moisture=fuel_model.live_fuel_moisture,
        surface_to_volume_ratio=fuel_model.surface_to_volume_ratio,
        heat_content_kj_kg=fuel_model.heat_content_kj_kg,
        mineral_content=fuel_model.mineral_content,
        moisture_extinction=fuel_model.moisture_extinction,
    )

    # Convert wind speed to m/s
    wind_speed_ms = wind_speed_kmh / 3.6

    # Calculate using Rothermel model
    return rothermel_spread_rate(
        fuel_model=adjusted_fuel,
        wind_speed_ms=wind_speed_ms,
        wind_direction_degrees=wind_direction_degrees,
        slope_degrees=slope_degrees,
    )


def estimate_time_to_area(
    current_area_hectares: float,
    target_area_hectares: float,
    spread_rate_m_per_min: float
) -> float:
    """
    Estimate time for fire to grow from current to target area.

    Args:
        current_area_hectares: Current fire size
        target_area_hectares: Target fire size
        spread_rate_m_per_min: Current spread rate

    Returns:
        Estimated hours to reach target area
    """
    if spread_rate_m_per_min <= 0 or target_area_hectares <= current_area_hectares:
        return 0.0

    # Simplified model: assume circular expansion
    current_radius_m = math.sqrt(current_area_hectares * 10000 / math.pi)
    target_radius_m = math.sqrt(target_area_hectares * 10000 / math.pi)

    radius_increase_m = target_radius_m - current_radius_m

    # Time = distance / rate
    time_minutes = radius_increase_m / spread_rate_m_per_min

    return time_minutes / 60  # Convert to hours
