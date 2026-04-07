# 🚁 Drone Delivery Environment

**OpenEnv-compatible** reinforcement learning environment for **multi-drone delivery fleet coordination**.

An LLM agent plans delivery routes across real city coordinates — managing weight capacity, battery constraints, and multi-drone coordination for heavy packages across a fleet of drones.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![HF Space](https://img.shields.io/badge/HuggingFace-Space-yellow)](https://huggingface.co/spaces)

---

## 🌍 Supported Cities (7 cities across 4 continents)

| City | Country | Depot |
|------|---------|-------|
| **Pune** | India | City Centre (18.5204, 73.8567) |
| **Mumbai** | India | CST Area (19.0760, 72.8777) |
| **Bangalore** | India | MG Road (12.9716, 77.5946) |
| **New York** | USA | Manhattan (40.7128, -74.0060) |
| **London** | UK | Charing Cross (51.5074, -0.1278) |
| **Tokyo** | Japan | Shinjuku (35.6762, 139.6503) |
| **Dubai** | UAE | Downtown (25.2048, 55.2708) |

## 🎯 Difficulty Levels

| Difficulty | Deliveries | Drones | Challenge |
|------------|-----------|--------|-----------|
| Easy       | 1         | 1      | Basic single-drone pathfinding |
| Medium     | 3         | 2      | Multi-drone routing + heavy packages requiring simultaneous visits |
| Hard       | 6–8       | 3      | Full TSP-style fleet coordination with battery management |

---

## 🏆 Reward Function (0.0 → 1.0)

| Component | Weight | Description |
|-----------|--------|-------------|
| Delivery completion | 0.55 | Fraction of deliveries successfully visited within 300m |
| Battery compliance | 0.25 | Total path distance within battery limit per drone |
| Efficiency bonus | 0.20 | Penalises excessive recharge trips vs optimal routing |

---

## 📐 Action Space

```json
{
  "drone_paths": [
    {
      "drone_id": 1,
      "waypoints": [
        {"lat": 18.5204, "lon": 73.8567},
        {"lat": 18.5314, "lon": 73.8446},
        {"lat": 18.5204, "lon": 73.8567}
      ]
    },
    {
      "drone_id": 2,
      "waypoints": [
        {"lat": 18.5204, "lon": 73.8567},
        {"lat": 18.5089, "lon": 73.8553},
        {"lat": 18.5204, "lon": 73.8567}
      ]
    }
  ]
}
```

- One `DronePath` per drone (exactly `num_drones` paths required)
- Every path must start and end at the depot
- Heavy packages (weight > drone capacity) require multiple drones visiting the same location simultaneously

## 👁️ Observation Space

```json
{
  "task_id": "pune_medium",
  "difficulty": "medium",
  "city": "Pune",
  "description": "2 drones, 3 packages including heavy item...",
  "depot_lat": 18.5204,
  "depot_lon": 73.8567,
  "num_drones": 2,
  "drone_weight_capacity_kg": 4.0,
  "battery_limit_km": 12.0,
  "delivery_locations": [
    {
      "id": "d1", "lat": 18.5314, "lon": 73.8446,
      "label": "Shivajinagar",
      "weight_kg": 2.0
    },
    {
      "id": "d2", "lat": 18.5089, "lon": 73.8553,
      "label": "Swargate",
      "weight_kg": 7.0
    }
  ],
  "no_fly_zones": [],
  "reward": 0.80,
  "done": true,
  "feedback": "📦 Deliveries: 3/3\n✅ Battery OK\n🏆 Total reward: 0.80"
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
| `/tasks` | GET | List all 21 available tasks |
| `/reset/custom` | POST | Start custom episode with your own depot/deliveries |
| `/web` | GET | Interactive map UI for manual testing |

---

## 📁 Project Structure

```
drone-delivery-env/
├── inference.py              # Baseline LLM agent (hackathon compliant)
├── models.py                 # Pydantic: DroneAction, DroneObservation, DroneState
├── openenv.yaml              # OpenEnv manifest
├── requirements.txt
├── Dockerfile                # HF Spaces ready (port 7860)
├── README.md
└── server/
    ├── __init__.py
    ├── app.py                # FastAPI server
    ├── drone_environment.py  # Core environment logic + reward computation
    └── web_ui.html           # Interactive map UI
```

---

## 🧠 Key Design Decisions

### Multi-drone coordination for heavy packages
Packages heavier than a single drone's capacity require multiple drones visiting the same coordinates simultaneously. For example, a 9kg package with 4kg-capacity drones needs 3 drones to all fly to the same location at once. This is the core novel challenge of the environment.

### Weight-aware battery simulation
Battery consumption is weight-adjusted: heavier loads consume more battery per km (3% extra per kg). Drones automatically return to depot to recharge when battery is insufficient to reach the next waypoint and return home safely.

### Real city coordinates across 4 continents
All depots and delivery locations use real GPS coordinates across 7 world cities — Pune, Mumbai, Bangalore, New York, London, Tokyo, and Dubai — making the routing challenge grounded in actual geography.

### Shaped reward signal
The reward provides dense partial credit at every step: partial delivery credit for completing some but not all deliveries, battery efficiency scoring, and an efficiency bonus that penalises unnecessary recharge trips.

---

## 📊 Baseline Results

Run `python inference.py` against a live environment to reproduce:

| City | Difficulty | Expected Reward |
|------|------------|-----------------|
| Pune | Easy | ~0.85–1.00 |
| Pune | Medium | ~0.55–0.75 |
| Pune | Hard | ~0.40–0.60 |
| Mumbai | Easy | ~0.85–1.00 |
| Mumbai | Medium | ~0.55–0.75 |
| Mumbai | Hard | ~0.40–0.60 |
| Bangalore | Easy | ~0.85–1.00 |
| Bangalore | Medium | ~0.55–0.75 |
| Bangalore | Hard | ~0.40–0.60 |
| New York | Easy | ~0.85–1.00 |
| New York | Medium | ~0.60–0.80 |
| New York | Hard | ~0.40–0.65 |
| London | Easy | ~0.85–1.00 |
| London | Medium | ~0.55–0.75 |
| London | Hard | ~0.40–0.60 |
| Tokyo | Easy | ~0.85–1.00 |
| Tokyo | Medium | ~0.55–0.75 |
| Tokyo | Hard | ~0.40–0.60 |
| Dubai | Easy | ~0.85–1.00 |
| Dubai | Medium | ~0.55–0.75 |
| Dubai | Hard | ~0.40–0.60 |

*Results vary by model. Tested with GPT-4o.*

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | LLM API endpoint | `https://api.openai.com/v1` |
| `MODEL_NAME` | Model identifier | `gpt-4o` |
| `HF_TOKEN` | API key | — |
| `ENV_URL` | Environment server URL | `http://localhost:7860` |
