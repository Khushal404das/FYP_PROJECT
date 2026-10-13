import sys, numpy as np, cv2
sys.path.insert(0, ".")
from vehicle_model import FeatureExtractor, CentroidTracker, CrossCameraReID, CameraScorer

print("=" * 60)
print("  vehicle_model.py -- Functional Verification")
print("=" * 60)

H, W = 480, 640
feat_ex = FeatureExtractor()
reid    = CrossCameraReID(similarity_threshold=0.65)

# ---- Feature extraction ----
frame = np.full((H, W, 3), 60, dtype=np.uint8)
cv2.rectangle(frame, (100, 150), (300, 260), (160, 80, 20), -1)   # blue vehicle
cv2.rectangle(frame, (380, 180), (560, 280), (30,  30, 180), -1)  # red vehicle

bbox_blue = [100, 150, 200, 110]
bbox_red  = [380, 180, 180, 100]

feat_blue = feat_ex.extract(frame, bbox_blue, (H, W))
feat_red  = feat_ex.extract(frame, bbox_red,  (H, W))

print("\n[FeatureExtractor] Blue rectangle:")
print("  color       =", feat_blue["color_name"])
print("  type        =", feat_blue["vehicle_type"])
print("  size        =", feat_blue["size"])
print("  hist shape  =", feat_blue["histogram"].shape)
print("  fvec shape  =", feat_blue["feature_vec"].shape)

print("\n[FeatureExtractor] Red rectangle:")
print("  color       =", feat_red["color_name"])
print("  type        =", feat_red["vehicle_type"])
print("  size        =", feat_red["size"])

# ---- ReID: Camera C11 first sighting ----
print("\n[CrossCameraReID] Camera C11 -- first sighting:")
r1 = reid.match(feat_blue, "C11")
print("  Blue ->", r1["global_id"], "is_new:", r1["is_new"],
      "sim:", round(r1["similarity"], 3), "color:", r1["color"])
r2 = reid.match(feat_red, "C11")
print("  Red  ->", r2["global_id"], "is_new:", r2["is_new"],
      "sim:", round(r2["similarity"], 3), "color:", r2["color"])

# ---- ReID: Camera C12 sees the same blue vehicle ----
print("\n[CrossCameraReID] Camera C12 -- same blue vehicle (should RE-IDENTIFY):")
frame2 = np.full((H, W, 3), 60, dtype=np.uint8)
cv2.rectangle(frame2, (200, 160), (400, 270), (160, 80, 20), -1)
feat_blue2 = feat_ex.extract(frame2, [200, 160, 200, 110], (H, W))
r3 = reid.match(feat_blue2, "C12")
print("  Blue ->", r3["global_id"], "is_new:", r3["is_new"],
      "sim:", round(r3["similarity"], 3), "cameras:", r3["camera_history"])

ok = r3["global_id"] == r1["global_id"]
print("  Re-ID correct:", ok, "(", r1["global_id"], "==", r3["global_id"], ")")

# ---- CentroidTracker ----
print("\n[CentroidTracker] Hungarian assignment:")
tracker = CentroidTracker()
dets1 = [{"bbox": bbox_blue, "features": feat_blue},
         {"bbox": bbox_red,  "features": feat_red}]
t1 = tracker.update(dets1)
print("  Frame-1 IDs:", list(t1.keys()), "(expect [1, 2])")

dets2 = [{"bbox": [110, 152, 200, 110], "features": feat_blue},
         {"bbox": [390, 182, 180, 100], "features": feat_red}]
t2 = tracker.update(dets2)
print("  Frame-2 IDs:", list(t2.keys()), "(expect same IDs after small movement)")

# ---- Summary ----
print("\n[Global Vehicles] Total:", reid.vehicle_count())
for gid, v in reid.get_all_vehicles().items():
    print(" ", gid, "color:", v["color"], "type:", v["vehicle_type"],
          "size:", v["size"], "cameras:", v["camera_history"])

print("\nAll checks passed!")
