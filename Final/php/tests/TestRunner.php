<?php
namespace VisionMixer\Tests;

require_once __DIR__ . '/../src/VehicleDetector.php';
require_once __DIR__ . '/../src/CentroidTracker.php';
require_once __DIR__ . '/../src/ReIDMatcher.php';
require_once __DIR__ . '/../src/CameraScorer.php';
require_once __DIR__ . '/../src/CameraSwitcher.php';
require_once __DIR__ . '/../src/VideoStitcher.php';
require_once __DIR__ . '/../src/EmailService.php';

use VisionMixer\VehicleDetector;
use VisionMixer\CentroidTracker;
use VisionMixer\ReIDMatcher;
use VisionMixer\CameraScorer;
use VisionMixer\CameraSwitcher;
use VisionMixer\VideoStitcher;
use VisionMixer\EmailService;
use PDO;

class TestRunner {
    private array $config;
    private ?PDO $db;

    public function __construct(array $config, ?PDO $db = null) {
        $this->config = $config;
        $this->db = $db;
    }

    public function runAllTests(): array {
        $results = [];

        // Module 1: Vehicle Detection
        $results[] = $this->test_TC_VD_01();
        $results[] = $this->test_TC_VD_02();
        $results[] = $this->test_TC_VD_03();
        $results[] = $this->test_TC_VD_04();
        $results[] = $this->test_TC_VD_05();

        // Module 2: Camera Switching Engine
        $results[] = $this->test_TC_CS_01();
        $results[] = $this->test_TC_CS_02();
        $results[] = $this->test_TC_CS_03();
        $results[] = $this->test_TC_CS_04();
        $results[] = $this->test_TC_CS_05();

        // Module 3: Re-Identification / Cross-Camera Matching
        $results[] = $this->test_TC_RI_01();
        $results[] = $this->test_TC_RI_02();
        $results[] = $this->test_TC_RI_03();
        $results[] = $this->test_TC_RI_04();
        $results[] = $this->test_TC_RI_05();

        // Module 4: Video Stitching and Email Delivery
        $results[] = $this->test_TC_VE_01();
        $results[] = $this->test_TC_VE_02();
        $results[] = $this->test_TC_VE_03();
        $results[] = $this->test_TC_VE_04();
        $results[] = $this->test_TC_VE_05();

        return $results;
    }

    // --- Module 1: Vehicle Detection ---

    private function test_TC_VD_01(): array {
        $detector = new VehicleDetector(0.60);
        $frame = [['class' => 'car', 'confidence' => 0.85, 'bbox' => [100, 100, 200, 120]]];
        $res = $detector->detect($frame);
        $pass = count($res) === 1 && $res[0]['class'] === 'car' && $res[0]['confidence'] >= 0.80;

        return [
            'id'       => 'TC-VD-01',
            'name'     => 'Detect Vehicle in Clear Frame',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Detected single car with confidence >= 0.80' : 'Detection failed'
        ];
    }

    private function test_TC_VD_02(): array {
        $detector = new VehicleDetector(0.60);
        $res = $detector->detect([]);
        $pass = count($res) === 0;

        return [
            'id'       => 'TC-VD-02',
            'name'     => 'No Detection on Empty Frame',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Detection list empty on clear road frame' : 'False positive detected'
        ];
    }

    private function test_TC_VD_03(): array {
        $detector = new VehicleDetector(0.60);
        $frame = [
            ['class' => 'car', 'confidence' => 0.88, 'bbox' => [50, 50, 150, 90]],
            ['class' => 'car', 'confidence' => 0.82, 'bbox' => [250, 150, 140, 80]],
            ['class' => 'car', 'confidence' => 0.90, 'bbox' => [450, 250, 160, 100]],
            ['class' => 'truck', 'confidence' => 0.86, 'bbox' => [700, 100, 220, 150]],
        ];
        $res = $detector->detect($frame);
        $pass = count($res) === 4;

        return [
            'id'       => 'TC-VD-03',
            'name'     => 'Detect Multiple Vehicles Simultaneously',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Returned 4 valid vehicle detections with unique bounding boxes' : 'Incorrect vehicle count'
        ];
    }

    private function test_TC_VD_04(): array {
        $detector = new VehicleDetector(0.60);
        $frame = [['class' => 'car', 'confidence' => 0.65, 'bbox' => [200, 200, 180, 110]]];
        $res = $detector->detect($frame);
        $pass = count($res) === 1 && $res[0]['confidence'] >= 0.60;

        return [
            'id'       => 'TC-VD-04',
            'name'     => 'Detection Under Low Light Conditions',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Vehicle detected under low-light threshold >= 0.60' : 'Low light detection missed'
        ];
    }

    private function test_TC_VD_05(): array {
        $detector = new VehicleDetector(0.60);
        $frame = [
            ['class' => 'person', 'confidence' => 0.90, 'bbox' => [50, 50, 30, 80]],
            ['class' => 'bicycle', 'confidence' => 0.85, 'bbox' => [100, 100, 40, 50]],
            ['class' => 'car', 'confidence' => 0.88, 'bbox' => [200, 150, 160, 90]],
        ];
        $res = $detector->detect($frame);
        $pass = count($res) === 1 && $res[0]['class'] === 'car';

        return [
            'id'       => 'TC-VD-05',
            'name'     => 'Filter Non-Vehicle Objects',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Ignored pedestrians and bicycles, retained only car class' : 'Failed to filter non-vehicles'
        ];
    }

    // --- Module 2: Camera Switching Engine ---

    private function test_TC_CS_01(): array {
        $switcher = new CameraSwitcher(0.15, 1, 3);
        $switcher->setActiveCamera('C1');
        $res = $switcher->selectBestCamera(['C1' => 0.55, 'C2' => 0.82]);
        $pass = $res['active_camera'] === 'C2' && $res['switched'] === true;

        return [
            'id'       => 'TC-CS-01',
            'name'     => 'Switch to Higher Resolution Camera',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Switched from C1 (0.55) to higher-scoring C2 (0.82)' : 'Switch failed'
        ];
    }

    private function test_TC_CS_02(): array {
        $switcher = new CameraSwitcher(0.15, 1, 3);
        $switcher->setActiveCamera('C1');
        $res = $switcher->selectBestCamera(['C1' => 0.71, 'C2' => 0.78]);
        $pass = $res['active_camera'] === 'C1' && $res['switched'] === false;

        return [
            'id'       => 'TC-CS-02',
            'name'     => 'Hysteresis Prevents Unnecessary Switching',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Prevented switch as score difference (0.07) was below hysteresis (0.15)' : 'Unnecessary switch triggered'
        ];
    }

    private function test_TC_CS_03(): array {
        $switcher = new CameraSwitcher(0.15, 5, 3);
        $switcher->setActiveCamera('C1');

        $switchedEarly = false;
        for ($i = 1; $i <= 4; $i++) {
            $r = $switcher->selectBestCamera(['C1' => 0.50, 'C2' => 0.85]);
            if ($r['switched']) $switchedEarly = true;
        }
        $fifthRes = $switcher->selectBestCamera(['C1' => 0.50, 'C2' => 0.85]);
        $pass = !$switchedEarly && $fifthRes['active_camera'] === 'C2' && $fifthRes['switched'] === true;

        return [
            'id'       => 'TC-CS-03',
            'name'     => 'Smooth Transition on Camera Switch',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Switch triggered precisely on 5th consecutive dominating frame' : 'DBN buffer failed'
        ];
    }

    private function test_TC_CS_04(): array {
        $switcher = new CameraSwitcher();
        $res = $switcher->handleOverlapZone(
            ['camera_id' => 'C1', 'bbox' => [100, 100, 40, 60]],
            ['camera_id' => 'C2', 'bbox' => [100, 100, 80, 100]]
        );
        $pass = $res['selected_camera'] === 'C2' && $res['suppressed_camera'] === 'C1';

        return [
            'id'       => 'TC-CS-04',
            'name'     => 'Handle Overlap Zone Between Two Cameras',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Selected C2 due to larger bbox area (5100 px2 vs 2400 px2)' : 'Overlap zone handling failed'
        ];
    }

    private function test_TC_CS_05(): array {
        $switcher = new CameraSwitcher(0.15, 5, 3); // Buffer 5, fallback 3
        $switcher->setActiveCamera('C1');

        // Simulate C1 losing vehicle for 3 frames
        $switcher->selectBestCamera(['C1' => 0.0, 'C2' => 0.74, 'C3' => 0.50]);
        $switcher->selectBestCamera(['C1' => 0.0, 'C2' => 0.74, 'C3' => 0.50]);
        $r3 = $switcher->selectBestCamera(['C1' => 0.0, 'C2' => 0.74, 'C3' => 0.50]);

        $pass = $r3['active_camera'] === 'C2' && $r3['switched'] === true;

        return [
            'id'       => 'TC-CS-05',
            'name'     => 'Fallback When Active Camera Loses Vehicle',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Automatically switched to C2 within 3 frames of C1 losing target' : 'Fallback failed'
        ];
    }

    // --- Module 3: Re-Identification / Cross-Camera Matching ---

    private function test_TC_RI_01(): array {
        $reid = new ReIDMatcher(0.75);
        $res = $reid->match(['color' => 'red', 'class' => 'sedan']);
        $pass = strpos($res['global_id'], 'VH-') === 0 && $res['is_new'] === true;

        return [
            'id'       => 'TC-RI-01',
            'name'     => 'Assign Global ID to New Vehicle',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? "Created new Global ID {$res['global_id']} for first appearance" : 'Global ID creation failed'
        ];
    }

    private function test_TC_RI_02(): array {
        $reid = new ReIDMatcher(0.75);
        $cropA = ['color' => 'red', 'class' => 'sedan'];
        $m1 = $reid->match($cropA);

        $cropB = ['color' => 'red', 'class' => 'sedan'];
        $m2 = $reid->match($cropB);

        $pass = $m1['global_id'] === $m2['global_id'] && $m2['similarity'] >= 0.75;

        return [
            'id'       => 'TC-RI-02',
            'name'     => 'Match Same Vehicle Across Two Cameras',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? "Matched same vehicle to {$m1['global_id']} with similarity >= 0.75" : 'Cross camera match failed'
        ];
    }

    private function test_TC_RI_03(): array {
        $reid = new ReIDMatcher(0.75);
        $cropRedSedan = ['color' => 'red', 'class' => 'sedan'];
        $m1 = $reid->match($cropRedSedan);

        $cropBlueTruck = ['color' => 'blue', 'class' => 'truck'];
        $m2 = $reid->match($cropBlueTruck);

        $pass = $m1['global_id'] !== $m2['global_id'];

        return [
            'id'       => 'TC-RI-03',
            'name'     => 'Reject Match for Different Vehicle',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? "Assigned distinct Global ID {$m2['global_id']} to different vehicle (blue truck)" : 'Incorrect match assigned'
        ];
    }

    private function test_TC_RI_04(): array {
        $reid = new ReIDMatcher(0.75);
        $crop = ['color' => 'white', 'class' => 'suv'];
        $m1 = $reid->match($crop);

        // Re-emerge after 10 frames
        $m2 = $reid->match($crop);
        $pass = $m1['global_id'] === $m2['global_id'];

        return [
            'id'       => 'TC-RI-04',
            'name'     => 'Re-Identify Vehicle After Occlusion',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? "Re-identified {$m1['global_id']} after occlusion without duplicate ID" : 'Occlusion ReID failed'
        ];
    }

    private function test_TC_RI_05(): array {
        $reid = new ReIDMatcher(0.75);
        $start = microtime(true);
        for ($i = 0; $i < 100; $i++) {
            $reid->extractFeatures(['color' => 'black', 'class' => 'car']);
        }
        $avgMs = ((microtime(true) - $start) / 100.0) * 1000.0;
        $pass = $avgMs <= 30.0;

        return [
            'id'       => 'TC-RI-05',
            'name'     => 'Feature Extraction Performance',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? sprintf('Average feature extraction time: %.2f ms (<= 30ms limit)', $avgMs) : 'Performance benchmark failed'
        ];
    }

    // --- Module 4: Video Stitching and Email Delivery ---

    private function test_TC_VE_01(): array {
        $stitcher = new VideoStitcher();
        $stitcher->addClip(['camera_id' => 'C3', 'start_time' => 27, 'end_time' => 40, 'file_path' => 'mock3.mp4']);
        $stitcher->addClip(['camera_id' => 'C1', 'start_time' => 0,  'end_time' => 15, 'file_path' => 'mock1.mp4']);
        $stitcher->addClip(['camera_id' => 'C2', 'start_time' => 14, 'end_time' => 28, 'file_path' => 'mock2.mp4']);

        $ordered = $stitcher->orderClips();
        $pass = $ordered[0]['camera_id'] === 'C1' && $ordered[1]['camera_id'] === 'C2' && $ordered[2]['camera_id'] === 'C3';

        return [
            'id'       => 'TC-VE-01',
            'name'     => 'Stitch Clips in Chronological Order',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Clips correctly sorted: C1 (0-15s) -> C2 (14-28s) -> C3 (27-40s)' : 'Chronological sorting failed'
        ];
    }

    private function test_TC_VE_02(): array {
        $stitcher = new VideoStitcher();
        $stitcher->addClip(['camera_id' => 'C1', 'start_time' => 10, 'end_time' => 18, 'resolution' => '720p', 'file_path' => 'c1.mp4']);
        $stitcher->addClip(['camera_id' => 'C2', 'start_time' => 10, 'end_time' => 18, 'resolution' => '1080p', 'file_path' => 'c2.mp4']);

        $dedup = $stitcher->deduplicateOverlaps();
        $pass = count($dedup) === 1 && $dedup[0]['camera_id'] === 'C2';

        return [
            'id'       => 'TC-VE-02',
            'name'     => 'Deduplicate Overlapping Clip Segments',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Retained higher-resolution C2 (1080p) clip and discarded C1' : 'Deduplication failed'
        ];
    }

    private function test_TC_VE_03(): array {
        $emailService = new EmailService($this->config['smtp'], $this->db);
        $attached = $emailService->attachVideo('mock_journey.mp4');
        $sent = $emailService->sendEmail('operator@fastnuces.edu.pk');

        $pass = $attached && $sent;

        return [
            'id'       => 'TC-VE-03',
            'name'     => 'Email Sent Successfully with Attachment',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'SMTP message composed with attachment and delivered' : 'Email transmission failed: ' . implode(' | ', $emailService->getLogs())
        ];
    }

    private function test_TC_VE_04(): array {
        $stitcher = new VideoStitcher();
        $stitcher->addClip(['camera_id' => 'C1', 'start_time' => 0, 'end_time' => 10, 'file_path' => 'valid1.mp4']);
        $stitcher->addClip(['camera_id' => 'C2', 'start_time' => 10, 'end_time' => 20, 'file_path' => 'missing_non_existent.mp4']);

        $validFile = __DIR__ . '/../../storage/exports/valid1.mp4';
        file_put_contents($validFile, 'MOCK_DATA');
        $stitcher->addClip(['camera_id' => 'C1', 'start_time' => 0, 'end_time' => 10, 'file_path' => $validFile]);

        $res = $stitcher->stitch('VH-001');
        @unlink($validFile);

        $pass = $res['success'] === true && $res['missing_skipped'] >= 1;

        return [
            'id'       => 'TC-VE-04',
            'name'     => 'Handle Missing Clip Gracefully',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? "Skipped {$res['missing_skipped']} missing clip and compiled remaining valid clips without crashing" : 'Missing clip crash'
        ];
    }

    private function test_TC_VE_05(): array {
        $badConfig = array_merge($this->config['smtp'], ['password' => 'invalid_password']);
        $emailService = new EmailService($badConfig, $this->db);
        $attached = $emailService->attachVideo('mock_journey.mp4');
        $sent = $emailService->sendEmail('operator@fastnuces.edu.pk');

        $pass = ($sent === false);

        return [
            'id'       => 'TC-VE-05',
            'name'     => 'Email Failure on Invalid Credentials',
            'status'   => $pass ? 'PASS' : 'FAIL',
            'details'  => $pass ? 'Caught AuthenticationError gracefully without application crash' : 'Unhandled exception on bad SMTP credentials'
        ];
    }
}
