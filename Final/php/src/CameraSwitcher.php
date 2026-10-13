<?php
namespace VisionMixer;

/**
 * CameraSwitcher
 * Implements intelligent camera switching using DBN frame buffer stability,
 * hysteresis thresholding, overlap deduplication, and automatic fallback.
 * Fully supports SRS FR-CS-02 to FR-CS-06 and Test Cases TC-CS-01 to TC-CS-05.
 */
class CameraSwitcher {
    private float $hysteresisThreshold;
    private int $dbnFrameBuffer;
    private int $fallbackFrames;

    private ?string $activeCamera = null;
    private ?string $candidateCamera = null;
    private int $candidateCount = 0;
    private int $activeMissedCount = 0;
    private array $scoreHistory = [];

    public function __construct(
        float $hysteresisThreshold = 0.15,
        int $dbnFrameBuffer = 5,
        int $fallbackFrames = 3
    ) {
        $this->hysteresisThreshold = $hysteresisThreshold;
        $this->dbnFrameBuffer = $dbnFrameBuffer;
        $this->fallbackFrames = $fallbackFrames;
    }

    public function getActiveCamera(): ?string {
        return $this->activeCamera;
    }

    public function setActiveCamera(?string $camId): void {
        $this->activeCamera = $camId;
        $this->candidateCamera = null;
        $this->candidateCount = 0;
        $this->activeMissedCount = 0;
    }

    /**
     * FR-CS-02, FR-CS-03, FR-CS-04, FR-CS-06:
     * Evaluates camera scores across active streams and returns switching decisions.
     *
     * @param array $cameraScores Map of camera_id => score (e.g. ['C11' => 0.55, 'C12' => 0.82])
     * @return array ['active_camera' => 'C12', 'switched' => true, 'reason' => 'Higher score exceeded hysteresis']
     */
    public function selectBestCamera(array $cameraScores): array {
        if (empty($cameraScores)) {
            return [
                'active_camera' => $this->activeCamera,
                'switched'      => false,
                'reason'        => 'No scores available'
            ];
        }

        // Store score history
        $this->scoreHistory[] = $cameraScores;
        if (count($this->scoreHistory) > 20) {
            array_shift($this->scoreHistory);
        }

        // Find highest scoring camera
        arsort($cameraScores);
        $bestCam = array_key_first($cameraScores);
        $bestScore = $cameraScores[$bestCam];

        // Initialize active camera if none set
        if ($this->activeCamera === null || !isset($cameraScores[$this->activeCamera])) {
            $this->setActiveCamera($bestCam);
            return [
                'active_camera' => $this->activeCamera,
                'switched'      => true,
                'reason'        => 'Initial active camera set'
            ];
        }

        $activeScore = $cameraScores[$this->activeCamera] ?? 0.0;

        // FR-CS-06 / TC-CS-05: Fallback when active camera loses vehicle
        if ($activeScore <= 0.01) {
            $this->activeMissedCount++;
            if ($this->activeMissedCount >= $this->fallbackFrames && $bestScore > 0.01) {
                $oldCam = $this->activeCamera;
                $this->setActiveCamera($bestCam);
                return [
                    'active_camera' => $this->activeCamera,
                    'switched'      => true,
                    'reason'        => "Fallback triggered: {$oldCam} lost vehicle for {$this->activeMissedCount} consecutive frames"
                ];
            }
        } else {
            $this->activeMissedCount = 0; // Reset missed counter
        }

        // If best camera is the current active camera
        if ($bestCam === $this->activeCamera) {
            $this->candidateCamera = null;
            $this->candidateCount = 0;
            return [
                'active_camera' => $this->activeCamera,
                'switched'      => false,
                'reason'        => 'Active camera remains optimal'
            ];
        }

        // FR-CS-03 / TC-CS-02: Check hysteresis threshold
        $scoreDiff = $bestScore - $activeScore;
        if ($scoreDiff < $this->hysteresisThreshold) {
            $this->candidateCamera = null;
            $this->candidateCount = 0;
            return [
                'active_camera' => $this->activeCamera,
                'switched'      => false,
                'reason'        => "Score difference ({$scoreDiff}) below hysteresis threshold ({$this->hysteresisThreshold})"
            ];
        }

        // FR-CS-04 / TC-CS-03: DBN Frame Buffer Stability
        if ($this->candidateCamera === $bestCam) {
            $this->candidateCount++;
        } else {
            $this->candidateCamera = $bestCam;
            $this->candidateCount = 1;
        }

        if ($this->candidateCount >= $this->dbnFrameBuffer) {
            $oldCam = $this->activeCamera;
            $this->setActiveCamera($bestCam);
            return [
                'active_camera' => $this->activeCamera,
                'switched'      => true,
                'reason'        => "Switch triggered: {$bestCam} score ({$bestScore}) exceeded {$oldCam} ({$activeScore}) for {$this->dbnFrameBuffer} consecutive frames"
            ];
        }

        return [
            'active_camera' => $this->activeCamera,
            'switched'      => false,
            'reason'        => "Candidate {$bestCam} dominates ({$this->candidateCount}/{$this->dbnFrameBuffer} frames required)"
        ];
    }

    /**
     * FR-CS-05 / TC-CS-04: Handle Overlap Zone Between Two Cameras
     * Selects the higher-scoring camera and suppresses lower-scoring feed.
     */
    public function handleOverlapZone(array $camADetection, array $camBDetection, float $weightA = 1.0, float $weightB = 1.0): array {
        $areaA = ($camADetection['bbox'][2] * $camADetection['bbox'][3]) * $weightA;
        $areaB = ($camBDetection['bbox'][2] * $camBDetection['bbox'][3]) * $weightB;

        if ($areaA >= $areaB) {
            return [
                'selected_camera'   => $camADetection['camera_id'],
                'suppressed_camera' => $camBDetection['camera_id'],
                'winning_bbox'      => $camADetection['bbox']
            ];
        } else {
            return [
                'selected_camera'   => $camBDetection['camera_id'],
                'suppressed_camera' => $camADetection['camera_id'],
                'winning_bbox'      => $camBDetection['bbox']
            ];
        }
    }
}
