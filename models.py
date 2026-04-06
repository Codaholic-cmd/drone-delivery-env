from typing import List, Optional
from pydantic import BaseModel, Field


class Waypoint(BaseModel):
    lat: float
    lon: float


class DronePath(BaseModel):
    drone_id: int = Field(..., description="Which drone this path belongs to (1-indexed)")
    waypoints: List[Waypoint] = Field(..., description="Ordered waypoints for this drone")


class DroneAction(BaseModel):
    """Action submitted by the agent: one path per drone."""
    drone_paths: List[DronePath] = Field(
        ...,
        description="One path per drone. Each drone starts at depot. "
                    "Heavy deliveries may require multiple drones visiting same location. "
                    "Each drone must return to depot at end."
    )


class DeliveryLocation(BaseModel):
    id: str
    lat: float
    lon: float
    label: str
    weight_kg: float = Field(default=1.0, description="Package weight in kg.")
    priority: str = Field(default="normal", description="urgent | normal | low")
    time_window_minutes: Optional[int] = Field(default=None, description="Must deliver within N minutes. None = no constraint.")


class NoFlyZone(BaseModel):
    id: str
    center_lat: float
    center_lon: float
    radius_km: float
    label: str


class DroneObservation(BaseModel):
    task_id: str
    difficulty: str
    city: str
    description: str

    depot_lat: float
    depot_lon: float
    num_drones: int = 1
    drone_weight_capacity_kg: float = Field(default=5.0, description="Max payload each drone can carry per trip (kg).")
    delivery_locations: List[DeliveryLocation]
    no_fly_zones: List[NoFlyZone]
    battery_limit_km: float
    drone_speed_kmh: float = 60.0

    reward: Optional[float] = None
    done: bool = False
    feedback: Optional[str] = None

    # Per-episode results
    deliveries_completed: Optional[int] = None
    total_deliveries: Optional[int] = None
    urgent_delivered: Optional[int] = None
    urgent_total: Optional[int] = None
    time_violations: Optional[int] = None
    no_fly_violations: Optional[int] = None
    duplicate_deliveries: Optional[int] = None
    per_drone_distance_km: Optional[List[float]] = None
    battery_exceeded_drones: Optional[List[int]] = None
    recharge_trips: Optional[int] = None


class DroneState(BaseModel):
    episode_id: str
    step_count: int = 0
    city: str = "New York"
    difficulty: str = "easy"
    task_id: str = ""
    num_drones: int = 1
    drone_weight_capacity_kg: float = 5.0
    submitted: bool = False
