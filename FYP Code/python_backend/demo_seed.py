"""
demo_seed.py — Seed demo tracking data for testing
===================================================
Run this ONCE to populate the tracking database with
synthetic vehicle tracks across multiple cameras so you
can use the PHP frontend without needing to process videos.

Usage:
    python demo_seed.py
"""

import sys, pickle, numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vehicle_tracker import VehicleTrackingPipeline, CAMERA_IDS, CAMERA_TOPOLOGY, TRACKS_DB

# Camera routes (vehicle journeys through the network)
DEMO_ROUTES = [
    # Vehicle 1 — passes through zone 1 → zone 2 → zone 4
    ["c11", "c12", "c21", "c22", "c41", "c42"],
    # Vehicle 2 — short route zone 2
    ["c21", "c23", "c24", "c51"],
    # Vehicle 3 — zone 3 → zone 4 → zone 6
    ["c31", "c32", "c41", "c43", "c61", "c62", "c63"],
    # Vehicle 4 — zone 1 only
    ["c11", "c12"],
    # Vehicle 5 — zone 5 → zone 6
    ["c51", "c52", "c61", "c64", "c65"],
    # Vehicle 6 — long journey
    ["c11", "c12", "c21", "c22", "c41", "c42", "c43", "c61", "c62", "c63", "c64", "c65"],
    # Vehicle 7 — zone 2 → zone 3
    ["c22", "c31", "c32"],
    # Vehicle 8 — zone 6
    ["c61", "c62"],
    # Vehicle 9 — zone 4 → zone 5
    ["c41", "c42", "c51", "c52"],
    # Vehicle 10 — zone 1 → zone 2 → zone 3
    ["c11", "c12", "c21", "c31", "c32"],
]

VEHICLE_METAS = [
    {"color": "white",  "vehicle_type": "car",         "plate": "ABC-1234"},
    {"color": "black",  "vehicle_type": "suv",         "plate": "XYZ-5678"},
    {"color": "silver", "vehicle_type": "truck",       "plate": "DEF-9012"},
    {"color": "red",    "vehicle_type": "motorcycle",  "plate": "GHI-3456"},
    {"color": "blue",   "vehicle_type": "van",         "plate": "JKL-7890"},
    {"color": "grey",   "vehicle_type": "car",         "plate": "MNO-2345"},
    {"color": "white",  "vehicle_type": "pickup",      "plate": "PQR-6789"},
    {"color": "brown",  "vehicle_type": "bus",         "plate": "STU-0123"},
    {"color": "orange", "vehicle_type": "car",         "plate": "VWX-4567"},
    {"color": "green",  "vehicle_type": "suv",         "plate": "YZA-8901"},
]


def make_feature(seed: int) -> np.ndarray:
    rng = np.random.RandomState(seed)
    f   = rng.rand(160).astype(np.float32)
    return f / np.linalg.norm(f)


def seed():
    pipeline = VehicleTrackingPipeline()
    reid     = pipeline.reid

    print("=" * 50)
    print("  Seeding demo vehicle tracking data...")
    print("=" * 50)

    for vid, route in enumerate(DEMO_ROUTES, start=1):
        feature = make_feature(vid * 42)
        meta    = VEHICLE_METAS[(vid - 1) % len(VEHICLE_METAS)]
        base_ts = float(vid * 15)  # spread out entry times

        gid = reid.next_gid
        reid.next_gid += 1

        sightings = []
        for step, cam in enumerate(route):
            ts = base_ts + step * 8.5
            sightings.append({
                "camera":    cam,
                "timestamp": round(ts, 1),
                "bbox":      [50 + step*10, 80, 120, 90],
            })

        cameras_set = set(route)
        reid.global_tracks[gid] = {
            "global_id":   gid,
            "feature":     feature,
            "last_camera": route[-1],
            "first_seen":  sightings[0]["timestamp"],
            "last_seen":   sightings[-1]["timestamp"],
            "cameras":     cameras_set,
            "sightings":   sightings,
            "meta":        meta,
        }

        print(f"  [+] Vehicle #{gid} | {meta['color']} {meta['vehicle_type']} "
              f"| Plate: {meta['plate']} | Route: {' -> '.join(c.upper() for c in route)}")

    pipeline._save_state()
    print()
    print(f"[OK] Seeded {len(DEMO_ROUTES)} vehicles. DB saved to: {TRACKS_DB}")
    print("     You can now open the PHP frontend to explore them.")


if __name__ == "__main__":
    seed()
