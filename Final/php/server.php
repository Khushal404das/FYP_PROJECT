<?php
/**
 * PHP Built-In Server Launcher & CLI Test Script
 */

$host = '127.0.0.1';
$port = 8000;
$publicDir = __DIR__ . '/public';

if (php_sapi_name() === 'cli') {
    if (isset($argv[1]) && $argv[1] === 'test') {
        echo "========================================================\n";
        echo " Running Agent-Based Vision Mixer Test Suite (PHP)\n";
        echo "========================================================\n\n";

        require_once __DIR__ . '/tests/TestRunner.php';
        $config = require __DIR__ . '/config/config.php';
        
        $runner = new \VisionMixer\Tests\TestRunner($config);
        $results = $runner->runAllTests();

        $passCount = 0;
        foreach ($results as $tc) {
            $statusStr = $tc['status'] === 'PASS' ? "\033[32m[ PASS ]\033[0m" : "\033[31m[ FAIL ]\033[0m";
            echo sprintf("%s %-10s %-45s - %s\n", $statusStr, $tc['id'], $tc['name'], $tc['details']);
            if ($tc['status'] === 'PASS') $passCount++;
        }

        echo "\n--------------------------------------------------------\n";
        echo sprintf(" Result: %d / %d Test Cases Passed (%.1f%%)\n", $passCount, count($results), ($passCount / count($results)) * 100);
        echo "--------------------------------------------------------\n";
        exit(0);
    }

    echo "Starting Vision Mixer PHP Server at http://{$host}:{$port}\n";
    echo "Document root: {$publicDir}\n";
    echo "Press Ctrl+C to stop.\n\n";

    passthru("php -S {$host}:{$port} -t " . escapeshellarg($publicDir));
}
