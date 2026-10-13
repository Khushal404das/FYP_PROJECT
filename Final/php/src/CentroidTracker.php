<?php
namespace VisionMixer;

/**
 * CentroidTracker
 * Assigns & maintains local track IDs across frames per camera.
 * Implements Kalman position prediction, occlusion tolerance, and stale track removal.
 * Fully supports SRS FR-TR-01 to FR-TR-04.
 */
class CentroidTracker {
    private int $nextTrackId = 1;
    private int $maxDisappeared;
    private int $maxDistance;

    private array $objects = [];     // track_id => [cx, cy]
    private array $bboxes = [];      // track_id => [x, y, w, h]
    private array $velocities = [];  // track_id => [vx, vy]
    private array $disappeared = []; // track_id => frames_missing
    private array $classes = [];     // track_id => vehicle_class

    public function __construct(int $maxDisappeared = 30, int $maxDistance = 80) {
        $this->maxDisappeared = $maxDisappeared;
        $this->maxDistance = $maxDistance;
    }

    public function register(array $centroid, array $bbox, string $class = 'car'): int {
        $trackId = $this->nextTrackId++;
        $this->objects[$trackId] = $centroid;
        $this->bboxes[$trackId] = $bbox;
        $this->velocities[$trackId] = [0, 0];
        $this->disappeared[$trackId] = 0;
        $this->classes[$trackId] = $class;
        return $trackId;
    }

    public function deregister(int $trackId): void {
        unset(
            $this->objects[$trackId],
            $this->bboxes[$trackId],
            $this->velocities[$trackId],
            $this->disappeared[$trackId],
            $this->classes[$trackId]
        );
    }

    /**
     * FR-TR-01, FR-TR-02, FR-TR-03, FR-TR-04:
     * Updates tracks with new bounding boxes detected in the frame.
     *
     * @param array $detections List of ['bbox' => [x,y,w,h], 'class' => 'car', ...]
     * @return array Map of trackId => ['centroid' => [cx,cy], 'bbox' => [x,y,w,h], 'class' => 'car']
     */
    public function update(array $detections): array {
        if (empty($detections)) {
            // FR-TR-03 / FR-TR-04: Predict next position and increment disappeared counter
            foreach (array_keys($this->disappeared) as $trackId) {
                $this->disappeared[$trackId]++;
                
                // Kalman prediction step: shift centroid by velocity
                $this->objects[$trackId][0] += $this->velocities[$trackId][0];
                $this->objects[$trackId][1] += $this->velocities[$trackId][1];

                if ($this->disappeared[$trackId] > $this->maxDisappeared) {
                    $this->deregister($trackId);
                }
            }
            return $this->getTracks();
        }

        // Compute input centroids
        $inputCentroids = [];
        foreach ($detections as $i => $det) {
            $b = $det['bbox'];
            $inputCentroids[$i] = [
                (int)($b[0] + $b[2] / 2),
                (int)($b[1] + $b[3] / 2)
            ];
        }

        if (empty($this->objects)) {
            foreach ($detections as $i => $det) {
                $this->register($inputCentroids[$i], $det['bbox'], $det['class'] ?? 'car');
            }
            return $this->getTracks();
        }

        // Distance matrix calculation between existing centroids and input centroids
        $trackIds = array_keys($this->objects);
        $distances = [];

        foreach ($trackIds as $rowIdx => $trackId) {
            $existing = $this->objects[$trackId];
            foreach ($inputCentroids as $colIdx => $input) {
                $dx = $existing[0] - $input[0];
                $dy = $existing[1] - $input[1];
                $distances[$rowIdx][$colIdx] = sqrt($dx * $dx + $dy * $dy);
            }
        }

        // Greedy matching
        $usedRows = [];
        $usedCols = [];

        // Sort pairs by distance
        $pairs = [];
        foreach ($distances as $r => $cols) {
            foreach ($cols as $c => $dist) {
                $pairs[] = ['row' => $r, 'col' => $c, 'dist' => $dist];
            }
        }
        usort($pairs, fn($a, $b) => $a['dist'] <=> $b['dist']);

        foreach ($pairs as $pair) {
            $r = $pair['row'];
            $c = $pair['col'];
            $dist = $pair['dist'];

            if (in_array($r, $usedRows, true) || in_array($c, $usedCols, true)) {
                continue;
            }

            if ($dist > $this->maxDistance) {
                continue;
            }

            $trackId = $trackIds[$r];
            $newCentroid = $inputCentroids[$c];

            // Velocity estimation (Kalman-like update)
            $this->velocities[$trackId] = [
                $newCentroid[0] - $this->objects[$trackId][0],
                $newCentroid[1] - $this->objects[$trackId][1]
            ];

            $this->objects[$trackId] = $newCentroid;
            $this->bboxes[$trackId] = $detections[$c]['bbox'];
            $this->classes[$trackId] = $detections[$c]['class'] ?? $this->classes[$trackId];
            $this->disappeared[$trackId] = 0;

            $usedRows[] = $r;
            $usedCols[] = $c;
        }

        // Unused existing tracks -> increment disappeared
        foreach ($trackIds as $r => $trackId) {
            if (!in_array($r, $usedRows, true)) {
                $this->disappeared[$trackId]++;
                // Position prediction
                $this->objects[$trackId][0] += $this->velocities[$trackId][0];
                $this->objects[$trackId][1] += $this->velocities[$trackId][1];

                if ($this->disappeared[$trackId] > $this->maxDisappeared) {
                    $this->deregister($trackId);
                }
            }
        }

        // Unused new centroids -> register
        foreach ($inputCentroids as $c => $centroid) {
            if (!in_array($c, $usedCols, true)) {
                $this->register($centroid, $detections[$c]['bbox'], $detections[$c]['class'] ?? 'car');
            }
        }

        return $this->getTracks();
    }

    public function getTracks(): array {
        $result = [];
        foreach ($this->objects as $trackId => $centroid) {
            $result[$trackId] = [
                'track_id'  => $trackId,
                'centroid'  => $centroid,
                'bbox'      => $this->bboxes[$trackId],
                'class'     => $this->classes[$trackId],
                'disappeared' => $this->disappeared[$trackId]
            ];
        }
        return $result;
    }
}
