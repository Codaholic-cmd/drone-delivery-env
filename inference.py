"""
inference.py — Baseline LLM agent for drone_delivery_env.
Compliant with OpenEnv Hackathon (Scaler x Meta PyTorch) evaluation format.
Emits [START], [STEP], [END] structured plain-text logs to stdout for automated scoring.
"""

import os
import json
import re
import sys
import time
import requests
from openai import OpenAI

# NO DEFAULT for HF_TOKEN to comply with the Pre-Submission Checklist
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN     = os.getenv("HF_TOKEN") 
ENV_URL      = os.getenv("ENV_URL", "https://sscodes101-drone-delivery-env.hf.space")

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
3. If a delivery weighs more than one drone's capacity, multiple drones must visit it simultaneously.
4. Each drone's total path distance must stay within the battery limit.
5. If a drone runs out of weight capacity mid-route, it must return to depot to pick up the next load.
6. Minimise total recharge trips for a better efficiency score.

OUTPUT FORMAT — return ONLY valid JSON:
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
Include one entry per drone even if a drone is idle.
"""

def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env=drone_delivery model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: str = None) -> None:
    err_str = error if error else "null"
    done_str = "true" if done else "false"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={err_str}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: list) -> None:
    succ_str = "true" if success else "false"
    rew_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.01"
    print(f"[END] success={succ_str} steps={steps} score={score:.2f} rewards={rew_str}", flush=True)

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
    text = re.sub(r"`{3}(?:json)?", "", llm_output).strip().rstrip("`").strip()
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
    log_start(task=task_id, model=MODEL_NAME)
    t0 = time.time()

    # 1. Reset Environment
    try:
        reset_resp = requests.post(f"{ENV_URL}/reset", json={"city": city, "difficulty": difficulty}, timeout=30)
        reset_resp.raise_for_status()
        obs = reset_resp.json()["observation"]
    except Exception as e:
        log_end(success=False, steps=1, score=0.01, rewards=[0.01]) # FIXED
        return {"task_id": task_id, "reward": 0.01, "error": f"reset failed: {e}"}

    n_drones = obs["num_drones"]
    depot = {"lat": obs["depot_lat"], "lon": obs["depot_lon"]}

    # 2. Get LLM Prediction
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_user_prompt(obs)}],
            temperature=0.1, max_tokens=2000,
        )
        llm_output = response.choices[0].message.content
    except Exception as e:
        err_msg = str(e).replace('\n', ' ')
        log_end(success=False, steps=1, score=0.01, rewards=[0.01]) # FIXED
        return {"task_id": task_id, "reward": 0.01, "error": f"llm failed: {err_msg}"}

    # 3. Parse output
    try:
        drone_paths = parse_drone_paths(llm_output, n_drones, depot)
    except Exception as e:
        log_end(success=False, steps=1, score=0.01, rewards=[0.01]) # FIXED
        return {"task_id": task_id, "reward": 0.01, "error": f"parse failed: {e}"}

    # 4. Step Environment
    try:
        step_resp = requests.post(f"{ENV_URL}/step", json={"drone_paths": drone_paths}, timeout=30)
        step_resp.raise_for_status()
        step_data = step_resp.json()
    except Exception as e:
        err_msg = str(e).replace('\n', ' ')
        log_end(success=False, steps=1, score=0.01, rewards=[0.01]) # FIXED
        return {"task_id": task_id, "reward": 0.01, "error": f"step failed: {err_msg}"}

    # 5. Extract Reward and Output Final Logs
    reward = float(step_data.get("reward", 0.01) or 0.01)
    
    # Ensure score is strictly clamped between 0.01 and 0.99
    score = max(0.01, min(0.99, reward))
    success = score > 0.05

    # Log the step and end sequences (PLAIN TEXT)
    log_step(step=1, action="submit_paths", reward=score, done=True, error=None)
    log_end(success=success, steps=1, score=score, rewards=[score])

    return {
        "task_id": task_id,
        "reward": score,
        "elapsed_seconds": round(time.time() - t0, 2)
    }

def main():
    try:
        health = requests.get(f"{ENV_URL}/health", timeout=10).json()
        cities = health.get("supported_cities", ["Pune", "Mumbai", "Bangalore", "New York", "London", "Tokyo", "Dubai"])
    except Exception as e:
        print(f"[ERROR] Health check failed: {e}", flush=True)
        sys.exit(1)

    all_results = []
    for city in cities:
        for difficulty in ["easy", "medium", "hard"]:
            task_id = f"{city.lower().replace(' ', '_')}_{difficulty}"
            r = run_task(task_id, city, difficulty)
            all_results.append(r)

    # Local JSON copy, strictly ignored by grader
    with open("inference_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

if __name__ == "__main__":
    main()
