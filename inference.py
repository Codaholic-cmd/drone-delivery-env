"""
inference.py — Baseline LLM agent for drone_delivery_env.

Compliant with OpenEnv Hackathon (Scaler x Meta PyTorch) evaluation format.
Emits [START], [STEP], [END] structured JSON logs to stdout for automated scoring.
"""

import os
import json
import re
import sys
import time
import requests
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.environ.get("HF_TOKEN", "")
ENV_URL      = os.environ.get("ENV_URL", "https://sscodes101-drone-delivery-env.hf.space")

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

SYSTEM_PROMPT = """You are an expert drone fleet route planner.

You will receive a delivery task with:
- A depot location (start and end point for all drones)
- A list of delivery locations with weights in kg
- Battery limit per drone (km)
- Drone capacity (kg) — max weight each drone can carry per trip
- Number of drones available

RULES:
1. Every drone path MUST start at the depot and end at the depot.
2. Each drone can only carry up to its weight capacity per trip.
3. If a delivery weighs more than one drone's capacity, multiple drones must visit it simultaneously (send multiple drones to the same coordinates).
4. Each drone's total path distance must stay within the battery limit.
5. If a drone runs out of weight capacity mid-route, it must return to depot to pick up the next load.
6. Minimise total recharge trips for a better efficiency score.

OUTPUT FORMAT — return ONLY valid JSON, no explanation:
{
  "drone_paths": [
    {
      "drone_id": 1,
      "waypoints": [
        {"lat": 40.7128, "lon": -74.0060},
        {"lat": 40.7282, "lon": -73.9942},
        {"lat": 40.7128, "lon": -74.0060}
      ]
    }
  ]
}

Include one entry per drone even if a drone is idle (give it a depot->depot path).
"""


def build_user_prompt(obs: dict) -> str:
    n = obs["num_drones"]
    cap = obs.get("drone_weight_capacity_kg", 5.0)
    lines = [
        f"City: {obs['city']} | Difficulty: {obs['difficulty']}",
        f"Task: {obs['description']}",
        "",
        f"Depot: lat={obs['depot_lat']}, lon={obs['depot_lon']}",
        f"Drones available: {n}",
        f"Battery limit per drone: {obs['battery_limit_km']} km",
        f"Weight capacity per drone: {cap} kg",
        f"\nDelivery locations ({len(obs['delivery_locations'])} total):",
    ]
    for d in obs["delivery_locations"]:
        weight = d.get("weight_kg", 1.0)
        drones_needed = max(1, -(-int(weight * 10) // int(cap * 10)))
        heavy_note = f" ⚠️ HEAVY — send {drones_needed} drones simultaneously" if weight > cap else ""
        lines.append(f"  - {d['label']}: lat={d['lat']}, lon={d['lon']} | {weight}kg{heavy_note}")
    lines.append(f"\nPlan paths for all {n} drone(s). Return JSON only.")
    return "\n".join(lines)


def parse_drone_paths(llm_output: str, n_drones: int, depot: dict):
    text = re.sub(r"```(?:json)?", "", llm_output).strip().rstrip("`").strip()
    parsed = None

    obj_match = re.search(r'\{.*\}', text, re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    if parsed is None:
        arr_match = re.search(r'\[.*\]', text, re.DOTALL)
        if arr_match:
            try:
                wps = json.loads(arr_match.group())
                parsed = {"drone_paths": [{"drone_id": 1, "waypoints": wps}]}
            except json.JSONDecodeError:
                pass

    if parsed is None:
        raise ValueError("No valid JSON found in LLM output")

    paths = parsed.get("drone_paths", [])
    existing_ids = {p["drone_id"] for p in paths}
    for i in range(1, n_drones + 1):
        if i not in existing_ids:
            paths.append({"drone_id": i, "waypoints": [depot, depot]})

    paths = sorted(paths, key=lambda p: p["drone_id"])[:n_drones]

    depot_wp = {"lat": depot["lat"], "lon": depot["lon"]}
    fixed = []
    for p in paths:
        wps = p.get("waypoints", [])
        if not wps or abs(wps[0].get("lat", 0) - depot["lat"]) > 0.001:
            wps = [depot_wp] + wps
        if len(wps) < 2 or abs(wps[-1].get("lat", 0) - depot["lat"]) > 0.001:
            wps = wps + [depot_wp]
        fixed.append({"drone_id": p["drone_id"], "waypoints": wps})
    return fixed


def run_task(task_id: str, city: str, difficulty: str) -> dict:
    # ── [START] ───────────────────────────────────────────────────────────────
    print(json.dumps({
        "type": "[START]",
        "task_id": task_id,
        "city": city,
        "difficulty": difficulty,
        "model": MODEL_NAME,
        "env_url": ENV_URL,
    }), flush=True)

    t0 = time.time()

    # 1. Reset
    try:
        reset_resp = requests.post(
            f"{ENV_URL}/reset",
            json={"city": city, "difficulty": difficulty},
            timeout=30,
        )
        reset_resp.raise_for_status()
        obs = reset_resp.json()["observation"]
    except Exception as e:
        result = {
            "type": "[END]",
            "task_id": task_id,
            "reward": 0.01,
            "deliveries_completed": 0,
            "total_deliveries": 0,
            "battery_exceeded_drones": [],
            "recharge_trips": 0,
            "error": f"reset failed: {e}",
            "elapsed_seconds": round(time.time() - t0, 2),
        }
        print(json.dumps(result), flush=True)
        return result

    n_drones = obs["num_drones"]
    depot = {"lat": obs["depot_lat"], "lon": obs["depot_lon"]}

    # 2. LLM
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(obs)},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        llm_output = response.choices[0].message.content
    except Exception as e:
        result = {
            "type": "[END]",
            "task_id": task_id,
            "reward": 0.01,
            "deliveries_completed": 0,
            "total_deliveries": len(obs.get("delivery_locations", [])),
            "battery_exceeded_drones": [],
            "recharge_trips": 0,
            "error": f"llm failed: {e}",
            "elapsed_seconds": round(time.time() - t0, 2),
        }
        print(json.dumps(result), flush=True)
        return result

    # 3. Parse
    try:
        drone_paths = parse_drone_paths(llm_output, n_drones, depot)
    except Exception as e:
        result = {
            "type": "[END]",
            "task_id": task_id,
            "reward": 0.01,
            "deliveries_completed": 0,
            "total_deliveries": len(obs.get("delivery_locations", [])),
            "battery_exceeded_drones": [],
            "recharge_trips": 0,
            "error": f"parse failed: {e}",
            "elapsed_seconds": round(time.time() - t0, 2),
        }
        print(json.dumps(result), flush=True)
        return result

    # ── [STEP] ────────────────────────────────────────────────────────────────
    print(json.dumps({
        "type": "[STEP]",
        "task_id": task_id,
        "n_drones": n_drones,
        "paths_summary": [
            {"drone_id": p["drone_id"], "n_waypoints": len(p["waypoints"])}
            for p in drone_paths
        ],
    }), flush=True)

    # 4. Step
    try:
        step_resp = requests.post(
            f"{ENV_URL}/step",
            json={"drone_paths": drone_paths},
            timeout=30,
        )
        step_resp.raise_for_status()
        step_data = step_resp.json()
    except Exception as e:
        result = {
            "type": "[END]",
            "task_id": task_id,
            "reward": 0.01,
            "deliveries_completed": 0,
            "total_deliveries": len(obs.get("delivery_locations", [])),
            "battery_exceeded_drones": [],
            "recharge_trips": 0,
            "error": f"step failed: {e}",
            "elapsed_seconds": round(time.time() - t0, 2),
        }
        print(json.dumps(result), flush=True)
        return result

    obs_out = step_data.get("observation", {})
    reward = float(step_data.get("reward", 0.01) or 0.01)
    # Ensure strictly in (0, 1) — never exactly 0.0 or 1.0
    reward = max(0.01, min(0.99, reward))

    # ── [END] ─────────────────────────────────────────────────────────────────
    result = {
        "type": "[END]",
        "task_id": task_id,
        "reward": round(reward, 4),
        "deliveries_completed": obs_out.get("deliveries_completed", 0),
        "total_deliveries": obs_out.get("total_deliveries", 0),
        "battery_exceeded_drones": obs_out.get("battery_exceeded_drones", []),
        "recharge_trips": obs_out.get("recharge_trips", 0),
        "per_drone_distance_km": obs_out.get("per_drone_distance_km", []),
        "feedback": obs_out.get("feedback", ""),
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    print(json.dumps(result), flush=True)
    return result


def main():
    try:
        health = requests.get(f"{ENV_URL}/health", timeout=10).json()
        cities = health.get("supported_cities", ["Pune", "Mumbai", "Bangalore", "New York", "London", "Tokyo", "Dubai"])
    except Exception as e:
        print(json.dumps({"type": "[ERROR]", "message": f"Health check failed: {e}"}), flush=True)
        sys.exit(1)

    all_results = []
    for city in cities:
        for difficulty in ["easy", "medium", "hard"]:
            task_id = f"{city.lower().replace(' ', '_')}_{difficulty}"
            try:
                r = run_task(task_id, city, difficulty)
                all_results.append(r)
            except Exception as e:
                err = {
                    "type": "[END]",
                    "task_id": task_id,
                    "reward": 0.01,
                    "deliveries_completed": 0,
                    "total_deliveries": 0,
                    "battery_exceeded_drones": [],
                    "recharge_trips": 0,
                    "error": str(e),
                    "elapsed_seconds": 0,
                }
                print(json.dumps(err), flush=True)
                all_results.append(err)

    rewards = [r.get("reward", 0.01) for r in all_results]
    avg_reward = sum(rewards) / len(rewards) if rewards else 0.01

    print(json.dumps({
        "type": "[SUMMARY]",
        "total_tasks": len(all_results),
        "average_reward": round(avg_reward, 4),
        "min_reward": round(min(rewards), 4) if rewards else 0.01,
        "max_reward": round(max(rewards), 4) if rewards else 0.01,
        "per_task": [
            {"task_id": r.get("task_id"), "reward": r.get("reward", 0.01)}
            for r in all_results
        ],
    }), flush=True)

    with open("inference_results.json", "w") as f:
        json.dump(all_results, f, indent=2)


if __name__ == "__main__":
    main()
