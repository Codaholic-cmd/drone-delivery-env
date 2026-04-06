# 🚁 Drone Delivery Environment

**OpenEnv-compatible** reinforcement learning environment for **multi-drone delivery fleet coordination**.

An LLM agent plans delivery routes across real city coordinates — managing weight capacity, battery constraints, no-fly zones, and urgent time windows across a fleet of drones.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![HF Space](https://img.shields.io/badge/HuggingFace-Space-yellow)](https://huggingface.co/spaces)

---

## 🌍 Supported Cities
- **New York** (Manhattan depot)
- **Mumbai** (CST area depot)
- **Pune** (City center depot)

## 🎯 Difficulty Levels

| Difficulty | Deliveries | Drones | No-Fly Zones | Challenge |
|------------|-----------|--------|--------------|-----------|
| Easy       | 1         | 1      | 0            | Basic single-drone pathfinding |
| Medium     | 3         | 2      | 1            | Multi-drone routing + heavy packages + NFZ avoidance |
| Hard       | 6–8       | 3      | 2–3          | Full TSP-style fleet coordination, recharging, time windows |

---

## 🏆 Reward Function (0.0 → 1.0)

| Component | Weight | Description |
|-----------|--------|-------------|
| Delivery completion | 0.35 | Fraction of deliveries successfully visited within 300m |
| Urgent deliveries | 0.20 | Fraction of urgent packages delivered on time |
| Time windows | 0.10 | No deliveries past their time window |
| No-fly compliance | 0.20 | No path segments enter restricted zones |
| Battery compliance | 0.10 | Total distance within battery limit per drone |
| Efficiency bonus | 0.05 | Path length vs greedy baseline (penalises excess recharges) |

---

## 📐 Action Space

```json
{
  "drone_paths": [
    {
      "drone_id": 1,
      "waypoints": [
        {"lat": 40.7128, "lon": -74.0060},
        {"lat": 40.7282, "lon": -73.9942},
        {"lat": 40.7128, "lon": -74.0060}
      ]
    },
    {
      "drone_id": 2,
      "waypoints": [
        {"lat": 40.7128, "lon": -74.0060},
        {"lat": 40.7484, "lon": -73.9967},
        {"lat": 40.7128, "lon": -74.0060}
      ]
    }
  ]
}
```

- One `DronePath` per drone (exactly `num_drones` paths required)
- Every path must start and end at the depot
- Drones carrying heavy packages (weight > capacity) return to depot for pickup between deliveries

## 👁️ Observation Space

```json
{
  "task_id": "new_york_medium",
  "difficulty": "medium",
  "city": "New York",
  "description": "2 drones, 3 packages including heavy item...",
  "depot_lat": 40.7128,
  "depot_lon": -74.0060,
  "num_drones": 2,
  "drone_weight_capacity_kg": 5.0,
  "battery_limit_km": 18.0,
  "delivery_locations": [
    {
      "id": "d1", "lat": 40.7282, "lon": -73.9942,
      "label": "Greenwich Village",
      "weight_kg": 1.5, "priority": "normal",
      "time_window_minutes": null
    }
  ],
  "no_fly_zones": [
    {
      "id": "nfz1",
      "center_lat": 40.7411, "center_lon": -74.0018,
      "radius_km": 0.8,
      "label": "Hudson Yards Airspace"
    }
  ],
  "reward": 0.85,
  "done": true,
  "feedback": "📦 Deliveries: 3/3\n✅ NFZ violations: 0\n✅ Battery OK"
}
```

---

## 🚀 Quick Start

### Run locally
```bash
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Run with Docker
```bash
docker build -t drone-delivery-env .
docker run -p 7860:7860 drone-delivery-env
```

### Run inference baseline
```bash
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o
export HF_TOKEN=your_api_key
export ENV_URL=http://localhost:7860

python inference.py
```

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + supported cities |
| `/reset` | POST | Start new episode (`city`, `difficulty`, optional `num_drones`) |
| `/step` | POST | Submit `drone_paths`, receive reward + feedback |
| `/state` | GET | Current episode metadata |
| `/tasks` | GET | List all 9 available tasks |
| `/reset/custom` | POST | Start custom episode with your own depot/deliveries/NFZs |
| `/web` | GET | Interactive map UI for manual testing |

---

## 📁 Project Structure

```
drone_delivery_env/
├── inference.py              # ← Baseline LLM agent (hackathon compliant)
├── models.py                 # Pydantic: DroneAction, DroneObservation, DroneState
├── openenv.yaml              # OpenEnv manifest
├── requirements.txt
├── Dockerfile                # HF Spaces ready (port 7860)
├── README.md
└── server/
    ├── app.py                # FastAPI server
    ├── drone_environment.py  # Core environment logic + reward computation
    └── web_ui.html           # Interactive map UI
```

---

## 🧠 Key Design Decisions

### Multi-drone coordination
The environment supports fleets of 1–5 drones. Heavy packages (weight > drone capacity) require multiple drones to visit the same location simultaneously — a realistic constraint for large cargo delivery.

### Weight-aware battery simulation
Battery consumption is weight-adjusted: heavier loads drain battery faster. Drones automatically return to depot when they run out of capacity, simulating realistic pickup-and-deliver cycles.

### Real city coordinates
All depots and delivery locations use real GPS coordinates in New York, Mumbai, and Pune — making the routing challenge grounded in actual geography.

### Shaped reward signal
The reward provides dense partial credit (not just 0/1), giving RL agents a meaningful gradient at every step:
- Partial delivery credit for completing some but not all deliveries
- Per-violation penalties for NFZ crossings and time window violations
- Battery efficiency signal comparing against greedy nearest-neighbour baseline

---

## 📊 Baseline Results

Run `python inference.py` against a live environment to reproduce:

| City | Difficulty | Expected Reward |
|------|------------|-----------------|
| New York | Easy | ~0.85–1.00 |
| New York | Medium | ~0.60–0.80 |
| New York | Hard | ~0.40–0.65 |
| Pune | Easy | ~0.85–1.00 |
| Pune | Medium | ~0.55–0.75 |
| Pune | Hard | ~0.40–0.60 |
| Mumbai | Easy | ~0.85–1.00 |
| Mumbai | Medium | ~0.55–0.75 |
| Mumbai | Hard | ~0.40–0.60 |

*Results vary by model. Tested with GPT-4o.*

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | LLM API endpoint | `https://api.openai.com/v1` |
| `MODEL_NAME` | Model identifier | `gpt-4o` |
| `HF_TOKEN` | Hugging Face / API key | — |
| `ENV_URL` | Environment server URL | `http://localhost:7860` |
