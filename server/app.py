import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import HTMLResponse, RedirectResponse

try:
    from models import DroneAction, DroneObservation, DroneState, DeliveryLocation, NoFlyZone, Waypoint
    from server.drone_environment import DroneDeliveryEnvironment, SUPPORTED_CITIES
except ImportError:
    from models import DroneAction, DroneObservation, DroneState, DeliveryLocation, NoFlyZone, Waypoint
    from server.drone_environment import DroneDeliveryEnvironment, SUPPORTED_CITIES

app = FastAPI(
    title="Drone Delivery Environment",
    description="Multi-drone delivery fleet coordination environment. OpenEnv-compatible.",
    version="3.0.0",
)
env = DroneDeliveryEnvironment()


class ResetRequest(BaseModel):
    city: Optional[str] = "New York"
    difficulty: Optional[str] = "easy"
    num_drones: Optional[int] = None


class CustomLocationIn(BaseModel):
    lat: float
    lon: float
    label: Optional[str] = "Custom"
    weight_kg: Optional[float] = 1.0
    priority: Optional[str] = "normal"
    time_window_minutes: Optional[int] = None


class CustomNoFlyZoneIn(BaseModel):
    lat: float
    lon: float
    radius_km: Optional[float] = 0.5
    label: Optional[str] = "Custom NFZ"


class CustomResetRequest(BaseModel):
    city: Optional[str] = "Custom"
    num_drones: Optional[int] = 1
    drone_weight_capacity_kg: Optional[float] = 5.0
    depot: CustomLocationIn
    deliveries: List[CustomLocationIn]
    no_fly_zones: Optional[List[CustomNoFlyZoneIn]] = []
    battery_limit_km: Optional[float] = 20.0


@app.get("/health")
def health():
    return {"status": "ok", "supported_cities": SUPPORTED_CITIES}

@app.get("/")
def root():
    return {
        "name": "Drone Delivery Environment",
        "version": "3.0.0",
        "status": "running",
        "endpoints": ["/health", "/reset", "/step", "/state", "/tasks", "/web"],
        "supported_cities": SUPPORTED_CITIES
    }


@app.post("/reset")
def reset(request: ResetRequest = ResetRequest()):
    obs = env.reset(city=request.city, difficulty=request.difficulty, num_drones=request.num_drones)
    return {
        "observation": obs.model_dump(),
        "reward": None, "done": False,
        "info": {"supported_cities": SUPPORTED_CITIES, "difficulties": ["easy", "medium", "hard"]}
    }


@app.post("/reset/custom")
def reset_custom(request: CustomResetRequest):
    import uuid as _uuid
    import math

    deliveries = [
        DeliveryLocation(
            id=f"d{i+1}", lat=d.lat, lon=d.lon,
            label=d.label or f"Delivery {i+1}",
            weight_kg=d.weight_kg or 1.0,
            priority=d.priority or "normal",
            time_window_minutes=d.time_window_minutes,
        )
        for i, d in enumerate(request.deliveries)
    ]
    nfzs = [
        NoFlyZone(
            id=f"nfz{i+1}", center_lat=n.lat, center_lon=n.lon,
            radius_km=n.radius_km, label=n.label or f"No-Fly Zone {i+1}"
        )
        for i, n in enumerate(request.no_fly_zones or [])
    ]
    n_drones = request.num_drones or 1
    capacity = request.drone_weight_capacity_kg or 5.0
    custom_task = {
        "deliveries": deliveries,
        "nfz": nfzs,
        "battery_km": request.battery_limit_km,
        "num_drones": n_drones,
        "drone_weight_capacity_kg": capacity,
        "description": f"Custom: {len(deliveries)} deliveries, {n_drones} drone(s), {capacity}kg cap, {len(nfzs)} NFZ(s).",
    }

    env._state = DroneState(
        episode_id=str(_uuid.uuid4()),
        city=request.city or "Custom", difficulty="custom",
        task_id="custom", num_drones=n_drones,
        drone_weight_capacity_kg=capacity,
    )
    env._depot = Waypoint(lat=request.depot.lat, lon=request.depot.lon)
    env._current_task = custom_task

    heavy = [d for d in deliveries if d.weight_kg > capacity]
    heavy_note = ""
    if heavy:
        heavy_note = " ⚠️ Heavy: " + ", ".join(
            f"{d.label}({d.weight_kg}kg→{math.ceil(d.weight_kg/capacity)} drones)"
            for d in heavy
        )

    obs = DroneObservation(
        task_id="custom", difficulty="custom", city=request.city or "Custom",
        description=custom_task["description"],
        depot_lat=request.depot.lat, depot_lon=request.depot.lon,
        num_drones=n_drones,
        drone_weight_capacity_kg=capacity,
        delivery_locations=deliveries, no_fly_zones=nfzs,
        battery_limit_km=request.battery_limit_km,
        done=False,
        feedback=f"Custom task loaded. {n_drones} drone(s), {capacity}kg cap each.{heavy_note} Plan paths and submit!",
    )
    return {"observation": obs.model_dump(), "reward": None, "done": False}


@app.post("/step")
def step(action: DroneAction):
    obs = env.step(action)
    return {
        "observation": obs.model_dump(),
        "reward": obs.reward, "done": obs.done,
        "info": {
            "deliveries_completed": obs.deliveries_completed,
            "total_deliveries": obs.total_deliveries,
            "urgent_delivered": obs.urgent_delivered,
            "time_violations": obs.time_violations,
            "no_fly_violations": obs.no_fly_violations,
            "duplicate_deliveries": obs.duplicate_deliveries,
            "per_drone_distance_km": obs.per_drone_distance_km,
            "battery_exceeded_drones": obs.battery_exceeded_drones,
            "recharge_trips": obs.recharge_trips,
        }
    }


@app.get("/state")
def state():
    return env.state().model_dump()


@app.get("/tasks")
def list_tasks():
    tasks = []
    for city in SUPPORTED_CITIES:
        for diff in ["easy", "medium", "hard"]:
            tasks.append({
                "task_id": f"{city.lower().replace(' ', '_')}_{diff}",
                "city": city,
                "difficulty": diff,
            })
    return {"tasks": tasks}


@app.get("/web", response_class=HTMLResponse)
def web_ui():
    html_path = os.path.join(os.path.dirname(__file__), "web_ui.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/")
def root():
    # Redirect visitors hitting the base URL straight to your Web UI
    return RedirectResponse(url="/web")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
