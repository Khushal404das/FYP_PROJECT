<?php
namespace VisionMixer;

/**
 * CameraScorer
 * Scores active camera views based on SRS formula:
 * score = (bbox_area / frame_area) * resolution_weight
 * enriched with active track count and frame sharpness.
 * Fully supports SRS FR-CS-01 to FR-CS-02 and Test Cases TC-CS-01 to TC-CS-05.
 */
class CameraScorer {
    private array $resolutionWeights;
    private int $frameWidth;
    private int $frameHeight;

    public function __construct(array $resolutionWeights = [], int $frameWidth = 1920, int $frameHeight = 1080) {
        $this->resolutionWeights = $resolutionWeights;
        $this->frameWidth = $frameWidth;
        $this->frameHeight = $frameHeight;
    }

    /**
     * FR-CS-01: Camera Score Calculation
     *
     * @param string $cameraId Camera ID (e.g. C11, C21)
     * @param array $tracks Array of tracked objects in camera
     * @param float $sharpness Laplacian sharpness variance (0 to 1)
     * @return float Calculated score (0.000 to 1.000)
     */
    public function calculateScore(string $cameraId, array $tracks, float $sharpness = 0.8): float {
        if (empty($tracks)) {
            return 0.0;
        }

        $resolutionWeight = $this->resolutionWeights[$cameraId] ?? 1.0;
        $frameArea = max(1, $this->frameWidth * $this->frameHeight);

        // Sum of bounding box areas
        $totalBboxArea = 0;
        foreach ($tracks as $track) {
            $bbox = $track['bbox'] ?? [0, 0, 100, 100];
            $w = $bbox[2] ?? 0;
            $h = $bbox[3] ?? 0;
            $totalBboxArea += ($w * $h);
        }

        // FR-CS-01 base formula: (bbox_area / frame_area) * wr
        $baseCoverageScore = ($totalBboxArea / $frameArea) * $resolutionWeight;
        $coverageNormalized = min(1.0, $baseCoverageScore * 4.5); // Scale up for score comparison

        // Track count factor
        $trackCountScore = min(1.0, count($tracks) / 5.0);

        // Weighted combination: 40% coverage, 40% track count, 20% sharpness
        $finalScore = ($coverageNormalized * 0.45) + ($trackCountScore * 0.35) + ($sharpness * 0.20);

        return round(min(1.0, max(0.0, $finalScore)), 3);
    }
}
