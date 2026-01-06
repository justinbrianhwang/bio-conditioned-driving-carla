import sys
import os
import time
import csv
import random
import gc

# ==================================================
# 1. CARLA 경로 설정 (import carla 이전에!)
# ==================================================
CARLA_ROOT = r"D:\coding\bio_carla\CARLA_0.9.13"

egg_path = os.path.join(
    CARLA_ROOT,
    "PythonAPI",
    "carla",
    "dist",
    "carla-0.9.13-py3.7-win-amd64.egg"
)

if egg_path not in sys.path:
    sys.path.append(egg_path)

# ==================================================
# 2. 이제 carla import
# ==================================================
import carla

# ===================== CONFIG =====================
RESULT_DIR = "results"
MAX_STEPS = 200                 # 안정화
FIXED_DELTA = 0.1               # 동기모드 tick
RISK_TAU = 0.7

MAX_IMAGES_PER_CASE = 5         # ★ 크래시 방지 핵심

# Robustness
LATENCIES = [0.0, 0.6, 1.0]
MISSING_RATES = [0.0, 0.2]
NOISE_STDS = [0.0, 0.1]

# OOD (안정 조합)
TOWNS = ["Town03", "Town05"]
WEATHERS = {
    "ClearNoon": carla.WeatherParameters.ClearNoon,
    "WetNoon": carla.WeatherParameters.WetNoon,
    "ClearNight": carla.WeatherParameters.ClearNight,
}

# ==================================================
from biosignal import BioSignalGenerator
from utils import apply_latency, apply_missing, apply_noise, ensure_dir


def set_sync_mode(world):
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = FIXED_DELTA
    world.apply_settings(settings)


def run_one_case(world, case_name, latency, miss_rate, noise_std):
    bp = world.get_blueprint_library()

    vehicle = None
    camera = None

    try:
        # ----------------------
        # Ego vehicle
        # ----------------------
        vehicle_bp = bp.filter("vehicle.tesla.model3")[0]
        spawn = world.get_map().get_spawn_points()[0]
        vehicle = world.spawn_actor(vehicle_bp, spawn)
        vehicle.set_autopilot(True)

        # ----------------------
        # Camera (chase view)
        # ----------------------
        cam_bp = bp.find("sensor.camera.rgb")
        cam_bp.set_attribute("image_size_x", "800")
        cam_bp.set_attribute("image_size_y", "600")
        cam_bp.set_attribute("fov", "90")

        cam_tf = carla.Transform(
            carla.Location(x=-7.5, z=3.0),
            carla.Rotation(pitch=-8.0, yaw=0.0)
        )

        camera = world.spawn_actor(cam_bp, cam_tf, attach_to=vehicle)
        latest = {"img": None}

        def cb(img):
            latest["img"] = img

        camera.listen(cb)

        # ----------------------
        # Bio + CSV
        # ----------------------
        bio = BioSignalGenerator()
        ensure_dir(RESULT_DIR)

        csv_path = os.path.join(RESULT_DIR, f"{case_name}.csv")
        saved = 0

        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["step", "risk", "HR", "HRV", "EDA"])

            for t in range(MAX_STEPS):
                world.tick()

                if latest["img"] is None:
                    continue

                # surrogate risk (논문에서는 TTC로 교체)
                risk = random.random()

                bio_sig = bio.step(risk)
                bio_sig = apply_latency(bio_sig, latency)
                bio_sig = apply_missing(bio_sig, miss_rate)
                bio_sig = apply_noise(bio_sig, noise_std)

                writer.writerow([
                    t,
                    risk,
                    bio_sig["HR"],
                    bio_sig["HRV"],
                    bio_sig["EDA"],
                ])

                # ----------------------
                # 논문용 이미지 자동 저장 (제한)
                # ----------------------
                if risk > RISK_TAU and saved < MAX_IMAGES_PER_CASE:
                    img_path = os.path.join(
                        RESULT_DIR,
                        f"{case_name}_img{saved}.png"
                    )
                    latest["img"].save_to_disk(img_path)
                    saved += 1

                time.sleep(FIXED_DELTA)

    except Exception as e:
        print(f"[ERROR] Case failed: {case_name}")
        print(e)

    finally:
        if camera is not None and camera.is_alive:
            camera.stop()
            camera.destroy()
        if vehicle is not None and vehicle.is_alive:
            vehicle.destroy()
        gc.collect()


def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)

    total_cases = (
        len(TOWNS)
        * len(WEATHERS)
        * len(LATENCIES)
        * len(MISSING_RATES)
        * len(NOISE_STDS)
    )

    print(f"[INFO] Total cases to run: {total_cases}")

    case_idx = 0

    for town in TOWNS:
        print(f"\n[TOWN] {town}")
        client.load_world(town)
        world = client.get_world()
        set_sync_mode(world)

        for w_name, weather in WEATHERS.items():
            print(f"  [WEATHER] {w_name}")
            world.set_weather(weather)

            for lat in LATENCIES:
                for miss in MISSING_RATES:
                    for noise in NOISE_STDS:
                        case_idx += 1
                        case = (
                            f"{town}_{w_name}"
                            f"_lat{lat}_miss{miss}_noise{noise}"
                        )

                        print(f"    [CASE {case_idx}/{total_cases}] {case}")
                        run_one_case(world, case, lat, miss, noise)

    print("\n[DONE] All cases finished successfully")


if __name__ == "__main__":
    main()
