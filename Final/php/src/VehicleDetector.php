<?php
namespace VisionMixer;

/**
 * VehicleDetector
 * Handles vehicle detection, class filtering (car, bus, truck, motorcycle),
 * confidence thresholding, and bounding box output.
 * Fully supports SRS FR-VD-01 to FR-VD-05 and Test Cases TC-VD-01 to TC-VD-05.
 */
class VehicleDetector {
    private float $confidenceThreshold;
    private array $allowedClasses = ['car', 'bus', 'truck', 'motorcycle'];

    public function __construct(float $confidenceThreshold = 0.60) {
        $this->confidenceThreshold = $confidenceThreshold;
    }

    /**
     * FR-VD-01, FR-VD-02, FR-VD-03, FR-VD-04:
     * Detects vehicles in a frame data array or frame description.
     * Filters out non-vehicle classes (pedestrians, cyclists, etc.)
     *
     * @param array $frameData Input frame or objects list
     * @return array List of bounding box detections [x, y, w, h, class, confidence]
     */
    public function detect(array $frameData): array {
        if (empty($frameData)) {
            return [];
        }

        $validDetections = [];

        foreach ($frameData as $obj) {
            $class = strtolower($obj['class'] ?? '');
            $confidence = (float)($obj['confidence'] ?? 0.0);
            $bbox = $obj['bbox'] ?? [0, 0, 0, 0]; // [x, y, w, h]

            // FR-VD-02 / TC-VD-05: Filter non-vehicle objects
            if (!in_array($class, $this->allowedClasses, true)) {
                continue;
            }

            // FR-VD-03: Filter by confidence threshold
            if ($confidence < $this->confidenceThreshold) {
                continue;
            }

            // Aspect ratio check (optional sanity check)
            $w = $bbox[2];
            $h = $bbox[3];
            if ($h > 0) {
                $aspect = $w / $h;
                if ($aspect < 0.3 || $aspect > 6.0) {
                    continue;
                }
            }

            // FR-VD-04: Output bounding box, class, and confidence
            $validDetections[] = [
                'bbox'       => $bbox,
                'class'      => $class,
                'confidence' => round($confidence, 2),
                'area'       => $w * $h
            ];
        }

        // Apply non-maximum suppression / deduplication on overlapping boxes
        return $this->mergeBoxes($validDetections);
    }

    /**
     * Greedy Non-Maximum Suppression (NMS) for overlapping boxes
     */
    private function mergeBoxes(array $detections, float $overlapThresh = 0.35): array {
        if (count($detections) <= 1) {
            return $detections;
        }

        // Sort by area descending
        usort($detections, fn($a, $b) => $b['area'] <=> $a['area']);

        $keep = [];
        while (!empty($detections)) {
            $first = array_shift($detections);
            $keep[] = $first;

            $remaining = [];
            foreach ($detections as $box) {
                $iou = $this->computeIoU($first['bbox'], $box['bbox']);
                if ($iou < $overlapThresh) {
                    $remaining[] = $box;
                }
            }
            $detections = $remaining;
        }

        return $keep;
    }

    private function computeIoU(array $boxA, array $boxB): float {
        $xA = max($boxA[0], $boxB[0]);
        $yA = max($boxA[1], $boxB[1]);
        $xB = min($boxA[0] + $boxA[2], $boxB[0] + $boxB[2]);
        $yB = min($boxA[1] + $boxA[3], $boxB[1] + $boxB[3]);

        $interArea = max(0, $xB - $xA) * max(0, $yB - $yA);
        $boxAArea = $boxA[2] * $boxA[3];
        $boxBArea = $boxB[2] * $boxB[3];

        $unionArea = $boxAArea + $boxBArea - $interArea;
        return $unionArea > 0 ? $interArea / $unionArea : 0.0;
    }
}
