import math
import uuid
from typing import List, Optional
from models import (
    DroneAction, DronePath, DroneObservation, DroneState,
    DeliveryLocation, Waypoint
)

def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def weight_factor(weight_kg: float) -> float:
    return 1.0 + 0.03 * weight_kg

def trips_needed(weight_kg: float, capacity_kg: float) -> int:
    return math.ceil(weight_kg / capacity_kg)

CITY_CONFIGS = {
    # ── INDIA ──────────────────────────────────────────────────────────────────
    "Pune": {
        "depot": (18.5204, 73.8567),
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 3.0,
            "deliveries": [DeliveryLocation(id="d1", lat=18.5314, lon=73.8446, label="Shivajinagar", weight_kg=1.0)],
            "battery_km": 10.0,
            "description": "1 drone (3kg cap), 1 package. Depot to Shivajinagar."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=18.5314, lon=73.8446, label="Shivajinagar", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=18.5089, lon=73.8553, label="Swargate", weight_kg=7.0),
                DeliveryLocation(id="d3", lat=18.5362, lon=73.8783, label="Koregaon Park", weight_kg=1.0),
            ],
            "battery_km": 12.0,
            "description": "2 drones (4kg cap). Swargate = 7kg needs 2 drones simultaneously."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=18.5314, lon=73.8446, label="Shivajinagar", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=18.5089, lon=73.8553, label="Swargate", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=18.5362, lon=73.8783, label="Koregaon Park", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=18.5642, lon=73.8019, label="Aundh", weight_kg=3.0),
                DeliveryLocation(id="d5", lat=18.4925, lon=73.8674, label="Hadapsar", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=18.5531, lon=73.8685, label="Viman Nagar", weight_kg=4.0),
            ],
            "battery_km": 18.0,
            "description": "3 drones (4kg cap). Swargate 9kg needs 3 drone trips. Full fleet coordination."
        },
    },
    "Mumbai": {
        "depot": (19.0760, 72.8777),
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 5.0,
            "deliveries": [DeliveryLocation(id="d1", lat=19.0896, lon=72.8656, label="Bandra", weight_kg=1.5)],
            "battery_km": 15.0,
            "description": "1 drone (5kg cap), 1 package. Depot to Bandra."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 5.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=19.0896, lon=72.8656, label="Bandra", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=19.1136, lon=72.8697, label="Andheri", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=19.0544, lon=72.8322, label="Worli", weight_kg=1.0),
            ],
            "battery_km": 20.0,
            "description": "2 drones (5kg cap). Andheri = 9kg, needs 2 drones simultaneously."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=19.0896, lon=72.8656, label="Bandra", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=19.1136, lon=72.8697, label="Andheri", weight_kg=7.0),
                DeliveryLocation(id="d3", lat=19.0544, lon=72.8322, label="Worli", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=19.1334, lon=72.9133, label="Powai", weight_kg=3.0),
                DeliveryLocation(id="d5", lat=19.0178, lon=72.8478, label="Dadar", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=19.0728, lon=72.8826, label="Kurla", weight_kg=4.0),
            ],
            "battery_km": 25.0,
            "description": "3 drones (4kg cap). 6 packages, Andheri 7kg needs 2 simultaneous drones."
        },
    },
    "Bangalore": {
        "depot": (12.9716, 77.5946),  # MG Road / City centre depot
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 4.0,
            "deliveries": [DeliveryLocation(id="d1", lat=12.9352, lon=77.6245, label="Koramangala", weight_kg=1.5)],
            "battery_km": 12.0,
            "description": "1 drone (4kg cap), 1 package. MG Road depot to Koramangala."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=12.9352, lon=77.6245, label="Koramangala", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=13.0358, lon=77.5970, label="Hebbal", weight_kg=7.5),
                DeliveryLocation(id="d3", lat=12.9698, lon=77.7499, label="Whitefield", weight_kg=1.0),
            ],
            "battery_km": 20.0,
            "description": "2 drones (4kg cap). Hebbal = 7.5kg needs 2 drones simultaneously. Spread across the city."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=12.9352, lon=77.6245, label="Koramangala", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=13.0358, lon=77.5970, label="Hebbal", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=12.9698, lon=77.7499, label="Whitefield", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=13.0297, lon=77.6848, label="Marthahalli", weight_kg=3.5),
                DeliveryLocation(id="d5", lat=12.9141, lon=77.6101, label="BTM Layout", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=13.0012, lon=77.5752, label="Yeshwanthpur", weight_kg=4.0),
            ],
            "battery_km": 28.0,
            "description": "3 drones (4kg cap). Hebbal 9kg needs 3 drone trips. Fleet coordination across Bangalore."
        },
    },
    # ── USA ────────────────────────────────────────────────────────────────────
    "New York": {
        "depot": (40.7128, -74.0060),
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 5.0,
            "deliveries": [DeliveryLocation(id="d1", lat=40.7282, lon=-73.9942, label="Greenwich Village", weight_kg=2.0)],
            "battery_km": 20.0,
            "description": "1 drone, 1 package. Manhattan depot to Greenwich Village."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 5.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=40.7282, lon=-73.9942, label="Greenwich Village", weight_kg=1.5),
                DeliveryLocation(id="d2", lat=40.7484, lon=-73.9967, label="Empire State Building", weight_kg=8.0),
                DeliveryLocation(id="d3", lat=40.7614, lon=-73.9776, label="Central Park South", weight_kg=0.5),
            ],
            "battery_km": 18.0,
            "description": "2 drones (5kg cap each). Empire State = 8kg — needs 2 drones simultaneously."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=40.7282, lon=-73.9942, label="Greenwich Village", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=40.7484, lon=-73.9967, label="Empire State Building", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=40.7614, lon=-73.9776, label="Central Park South", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=40.7831, lon=-73.9712, label="Upper West Side", weight_kg=3.0),
                DeliveryLocation(id="d5", lat=40.7679, lon=-73.9441, label="East Harlem", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=40.7549, lon=-73.9840, label="Times Square", weight_kg=4.0),
                DeliveryLocation(id="d7", lat=40.7061, lon=-74.0087, label="Financial District", weight_kg=6.0),
                DeliveryLocation(id="d8", lat=40.7193, lon=-73.9951, label="Tribeca", weight_kg=1.5),
            ],
            "battery_km": 20.0,
            "description": "3 drones (4kg cap). 8 packages, several over capacity requiring multi-drone coordination."
        },
    },
    # ── UK ─────────────────────────────────────────────────────────────────────
    "London": {
        "depot": (51.5074, -0.1278),  # Central London / Charing Cross depot
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 5.0,
            "deliveries": [DeliveryLocation(id="d1", lat=51.5155, lon=-0.0922, label="Shoreditch", weight_kg=2.0)],
            "battery_km": 15.0,
            "description": "1 drone (5kg cap), 1 package. Central London depot to Shoreditch."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 5.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=51.5155, lon=-0.0922, label="Shoreditch", weight_kg=1.5),
                DeliveryLocation(id="d2", lat=51.4994, lon=-0.1248, label="Westminster", weight_kg=8.5),
                DeliveryLocation(id="d3", lat=51.5033, lon=-0.0754, label="Canary Wharf", weight_kg=1.0),
            ],
            "battery_km": 20.0,
            "description": "2 drones (5kg cap). Westminster = 8.5kg needs 2 drones simultaneously."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=51.5155, lon=-0.0922, label="Shoreditch", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=51.4994, lon=-0.1248, label="Westminster", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=51.5033, lon=-0.0754, label="Canary Wharf", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=51.4613, lon=-0.1156, label="Brixton", weight_kg=3.0),
                DeliveryLocation(id="d5", lat=51.5560, lon=-0.1087, label="Islington", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=51.4816, lon=-0.1910, label="Hammersmith", weight_kg=4.0),
            ],
            "battery_km": 25.0,
            "description": "3 drones (4kg cap). Westminster 9kg needs 3 drone trips. London-wide fleet coordination."
        },
    },
    # ── JAPAN ──────────────────────────────────────────────────────────────────
    "Tokyo": {
        "depot": (35.6762, 139.6503),  # Shinjuku station depot
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 5.0,
            "deliveries": [DeliveryLocation(id="d1", lat=35.7100, lon=139.8107, label="Asakusa", weight_kg=2.0)],
            "battery_km": 20.0,
            "description": "1 drone (5kg cap), 1 package. Shinjuku depot to Asakusa."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 5.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=35.7100, lon=139.8107, label="Asakusa", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=35.6585, lon=139.7454, label="Shibuya", weight_kg=8.0),
                DeliveryLocation(id="d3", lat=35.7291, lon=139.7174, label="Ikebukuro", weight_kg=1.0),
            ],
            "battery_km": 22.0,
            "description": "2 drones (5kg cap). Shibuya = 8kg needs 2 drones simultaneously."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=35.7100, lon=139.8107, label="Asakusa", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=35.6585, lon=139.7454, label="Shibuya", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=35.7291, lon=139.7174, label="Ikebukuro", weight_kg=1.0),
                DeliveryLocation(id="d4", lat=35.6594, lon=139.7006, label="Setagaya", weight_kg=3.5),
                DeliveryLocation(id="d5", lat=35.6197, lon=139.7280, label="Shinagawa", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=35.6952, lon=139.7744, label="Akihabara", weight_kg=4.0),
            ],
            "battery_km": 28.0,
            "description": "3 drones (4kg cap). Shibuya 9kg needs 3 drone trips. Tokyo-wide fleet coordination."
        },
    },
    # ── UAE ────────────────────────────────────────────────────────────────────
    "Dubai": {
        "depot": (25.2048, 55.2708),  # Downtown Dubai / Burj Khalifa area depot
        "easy": {
            "num_drones": 1, "drone_weight_capacity_kg": 5.0,
            "deliveries": [DeliveryLocation(id="d1", lat=25.1972, lon=55.2796, label="Business Bay", weight_kg=2.0)],
            "battery_km": 15.0,
            "description": "1 drone (5kg cap), 1 package. Downtown Dubai depot to Business Bay."
        },
        "medium": {
            "num_drones": 2, "drone_weight_capacity_kg": 5.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=25.1972, lon=55.2796, label="Business Bay", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=25.2285, lon=55.3273, label="Deira", weight_kg=8.0),
                DeliveryLocation(id="d3", lat=25.1124, lon=55.1390, label="Dubai Marina", weight_kg=1.5),
            ],
            "battery_km": 25.0,
            "description": "2 drones (5kg cap). Deira = 8kg needs 2 drones simultaneously. City spans 25km."
        },
        "hard": {
            "num_drones": 3, "drone_weight_capacity_kg": 4.0,
            "deliveries": [
                DeliveryLocation(id="d1", lat=25.1972, lon=55.2796, label="Business Bay", weight_kg=2.0),
                DeliveryLocation(id="d2", lat=25.2285, lon=55.3273, label="Deira", weight_kg=9.0),
                DeliveryLocation(id="d3", lat=25.1124, lon=55.1390, label="Dubai Marina", weight_kg=1.5),
                DeliveryLocation(id="d4", lat=25.1177, lon=55.2003, label="Jumeirah", weight_kg=3.0),
                DeliveryLocation(id="d5", lat=25.2631, lon=55.3172, label="Al Qusais", weight_kg=0.5),
                DeliveryLocation(id="d6", lat=25.1864, lon=55.2752, label="Karama", weight_kg=4.0),
            ],
            "battery_km": 35.0,
            "description": "3 drones (4kg cap). Deira 9kg needs 3 drone trips. Spread across the Dubai urban corridor."
        },
    },
}

SUPPORTED_CITIES = list(CITY_CONFIGS.keys())
DRONE_SPEED_KMH = 60.0
VISIT_RADIUS_KM = 0.3
RETURN_SAFETY_FACTOR = 1.05


class DroneDeliveryEnvironment:
    def __init__(self):
        self._state = DroneState(episode_id=str(uuid.uuid4()))
        self._current_task = None
        self._depot = None

    def reset(self, city: str = "New York", difficulty: str = "easy", num_drones: Optional[int] = None) -> DroneObservation:
        city = city.strip().title()
        if city not in CITY_CONFIGS:
            city = "New York"
        difficulty = difficulty.lower()
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "easy"

        cfg = CITY_CONFIGS[city]
        task = cfg[difficulty]
        n_drones = num_drones if num_drones and num_drones > 0 else task["num_drones"]
        capacity = task.get("drone_weight_capacity_kg", 5.0)

        self._state = DroneState(
            episode_id=str(uuid.uuid4()), city=city, difficulty=difficulty,
            task_id=f"{city.lower().replace(' ','_')}_{difficulty}",
            num_drones=n_drones, drone_weight_capacity_kg=capacity,
        )
        depot_lat, depot_lon = cfg["depot"]
        self._depot = Waypoint(lat=depot_lat, lon=depot_lon)
        self._current_task = {**task, "num_drones": n_drones}

        return DroneObservation(
            task_id=self._state.task_id, difficulty=difficulty, city=city,
            description=task["description"],
            depot_lat=depot_lat, depot_lon=depot_lon,
            num_drones=n_drones, drone_weight_capacity_kg=capacity,
            delivery_locations=task["deliveries"], no_fly_zones=[],
            battery_limit_km=task["battery_km"], drone_speed_kmh=DRONE_SPEED_KMH,
            done=False,
            feedback=f"Task reset. {n_drones} drone(s), {capacity}kg capacity each. Submit {n_drones} path(s) via step().",
        )

    def step(self, action: DroneAction) -> DroneObservation:
        self._state.step_count += 1
        task = self._current_task
        deliveries: List[DeliveryLocation] = task["deliveries"]
        battery_limit: float = task["battery_km"]
        capacity_kg: float = task.get("drone_weight_capacity_kg", 5.0)
        n_drones = task["num_drones"]
        depot = self._depot

        if len(action.drone_paths) != n_drones:
            return self._error_obs(f"Expected {n_drones} drone path(s), got {len(action.drone_paths)}.")

        delivery_visits: dict = {}
        delivery_trips_needed: dict = {}
        skipped_deliveries: set = set()
        for d in deliveries:
            needed = trips_needed(d.weight_kg, capacity_kg)
            delivery_trips_needed[d.id] = needed
            delivery_visits[d.id] = set()
            if needed > n_drones:
                skipped_deliveries.add(d.id)

        all_completed_deliveries: set = set()
        per_drone_dist = []
        battery_exceeded_drones = []
        total_recharge_trips = 0

        for dp in action.drone_paths:
            wps = dp.waypoints
            if not wps:
                per_drone_dist.append(0.0)
                continue

            battery_remaining = battery_limit
            current_weight = 0.0
            dist = 0.0
            recharge_count = 0
            drone_lat, drone_lon = wps[0].lat, wps[0].lon

            i = 0
            while i < len(wps) - 1:
                next_wp = wps[i + 1]
                seg_dist = haversine(drone_lat, drone_lon, next_wp.lat, next_wp.lon)
                dist_to_home_from_next = haversine(next_wp.lat, next_wp.lon, depot.lat, depot.lon)
                battery_cost = seg_dist * weight_factor(current_weight)
                return_cost_from_next = dist_to_home_from_next * weight_factor(0) * RETURN_SAFETY_FACTOR

                if battery_remaining - battery_cost < return_cost_from_next:
                    dist_back = haversine(drone_lat, drone_lon, depot.lat, depot.lon)
                    dist += dist_back
                    battery_remaining = battery_limit
                    current_weight = 0.0
                    recharge_count += 1
                    drone_lat, drone_lon = depot.lat, depot.lon
                    seg_dist_from_depot = haversine(depot.lat, depot.lon, next_wp.lat, next_wp.lon)
                    if seg_dist_from_depot * weight_factor(0) * RETURN_SAFETY_FACTOR * 2 > battery_limit:
                        i += 1
                    continue

                battery_remaining -= battery_cost
                dist += seg_dist
                drone_lat, drone_lon = next_wp.lat, next_wp.lon
                i += 1

                for d in deliveries:
                    if d.id not in skipped_deliveries and haversine(drone_lat, drone_lon, d.lat, d.lon) <= VISIT_RADIUS_KM:
                        delivery_visits[d.id].add(dp.drone_id)
                        current_weight = max(0, current_weight - min(d.weight_kg, capacity_kg))

            if wps:
                dist_home = haversine(drone_lat, drone_lon, depot.lat, depot.lon)
                dist += dist_home
                battery_remaining -= dist_home * weight_factor(current_weight)

            per_drone_dist.append(round(dist, 3))
            total_recharge_trips += recharge_count
            if battery_remaining < -0.5:
                battery_exceeded_drones.append(dp.drone_id)

        for d in deliveries:
            if d.id in skipped_deliveries:
                continue
            if len(delivery_visits[d.id]) >= delivery_trips_needed[d.id]:
                all_completed_deliveries.add(d.id)

        n_delivered = len(all_completed_deliveries)
        n_total = len(deliveries)

        # Reward: delivery 0.55 + battery 0.25 + efficiency 0.20 = 1.0
        delivery_score  = 0.55 * (n_delivered / n_total)
        battery_score   = 0.25 * (1 - len(battery_exceeded_drones) / n_drones)
        recharge_penalty = min(0.20, 0.04 * total_recharge_trips)
        efficiency_score = max(0, 0.20 - recharge_penalty)
        reward = round(delivery_score + battery_score + efficiency_score, 4)
        reward = max(0.01, min(0.99, reward))

        heavy = [d for d in deliveries if d.weight_kg > capacity_kg and d.id not in skipped_deliveries]
        heavy_info = ""
        if heavy:
            heavy_info = "\n🏋️ Heavy (multi-drone needed): " + ", ".join(
                f"{d.label} ({d.weight_kg}kg → {delivery_trips_needed[d.id]} drones, visited by {len(delivery_visits[d.id])})"
                for d in heavy
            )
        skip_info = ""
        if skipped_deliveries:
            skip_names = [d.label for d in deliveries if d.id in skipped_deliveries]
            skip_info = f"\n❌ Skipped (need more drones): {', '.join(skip_names)}"

        lines = [
            f"🚁 Drones used: {n_drones} | Capacity: {capacity_kg}kg each",
            f"📦 Deliveries: {n_delivered}/{n_total - len(skipped_deliveries)}",
            f"{'✅' if not battery_exceeded_drones else '❌'} Battery exceeded: {battery_exceeded_drones or 'None'}",
            f"🔋 Recharge trips: {total_recharge_trips}",
            f"📏 Per-drone distance (incl. return): {per_drone_dist} km",
            heavy_info, skip_info,
            f"🏆 Total reward: {reward}",
        ]

        return DroneObservation(
            task_id=self._state.task_id, difficulty=self._state.difficulty, city=self._state.city,
            description=task["description"],
            depot_lat=depot.lat, depot_lon=depot.lon,
            num_drones=n_drones, drone_weight_capacity_kg=capacity_kg,
            delivery_locations=deliveries, no_fly_zones=[],
            battery_limit_km=battery_limit, drone_speed_kmh=DRONE_SPEED_KMH,
            reward=reward, done=True,
            feedback="\n".join(l for l in lines if l),
            deliveries_completed=n_delivered, total_deliveries=n_total,
            urgent_delivered=0, urgent_total=0,
            time_violations=0, no_fly_violations=0, duplicate_deliveries=0,
            per_drone_distance_km=per_drone_dist,
            battery_exceeded_drones=battery_exceeded_drones,
            recharge_trips=total_recharge_trips,
        )

    def _error_obs(self, msg: str) -> DroneObservation:
        task = self._current_task
        return DroneObservation(
            task_id=self._state.task_id, difficulty=self._state.difficulty, city=self._state.city,
            description=msg,
            depot_lat=self._depot.lat, depot_lon=self._depot.lon,
            num_drones=task["num_drones"],
            drone_weight_capacity_kg=task.get("drone_weight_capacity_kg", 5.0),
            delivery_locations=task["deliveries"], no_fly_zones=[],
            battery_limit_km=task["battery_km"],
            reward=0.0, done=True, feedback=f"ERROR: {msg}",
        )

    def state(self) -> DroneState:
        return self._state
