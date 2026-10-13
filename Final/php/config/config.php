<?php
/**
 * Global Configuration for Agent-Based Vision-Mixer System
 */

return [
    'app' => [
        'name' => 'Agent Based Vision-Mixer for Video Broadcasts',
        'version' => '1.0.0',
        'env' => 'development',
        'base_url' => 'http://localhost:8000',
    ],

    'database' => [
        'driver' => 'sqlite',
        'path' => __DIR__ . '/../../database.sqlite',
    ],

    'cameras' => [
        'C11' => ['name' => 'Camera 11 (Main Entrance)', 'zone' => 'Zone 1', 'resolution_weight' => 1.0, 'file' => 'camera_c11.mp4'],
        'C12' => ['name' => 'Camera 12 (North Gate)',     'zone' => 'Zone 1', 'resolution_weight' => 0.9, 'file' => 'camera_c12.mp4'],
        'C21' => ['name' => 'Camera 21 (East Boulevard)', 'zone' => 'Zone 2', 'resolution_weight' => 1.2, 'file' => 'camera_c21.mp4'],
        'C22' => ['name' => 'Camera 22 (East Junction)',  'zone' => 'Zone 2', 'resolution_weight' => 1.0, 'file' => 'camera_c22.mp4'],
        'C23' => ['name' => 'Camera 23 (East Parking)',   'zone' => 'Zone 2', 'resolution_weight' => 0.8, 'file' => 'camera_c23.mp4'],
        'C24' => ['name' => 'Camera 24 (East Exit)',      'zone' => 'Zone 2', 'resolution_weight' => 1.1, 'file' => 'camera_c24.mp4'],
        'C31' => ['name' => 'Camera 31 (West Avenue)',    'zone' => 'Zone 3', 'resolution_weight' => 1.0, 'file' => 'camera_c31.mp4'],
        'C32' => ['name' => 'Camera 32 (West Cross)',     'zone' => 'Zone 3', 'resolution_weight' => 0.9, 'file' => 'camera_c32.mp4'],
        'C41' => ['name' => 'Camera 41 (South Ring)',     'zone' => 'Zone 4', 'resolution_weight' => 1.1, 'file' => 'camera_c41.mp4'],
        'C42' => ['name' => 'Camera 42 (South Depot)',    'zone' => 'Zone 4', 'resolution_weight' => 0.85,'file' => 'camera_c42.mp4'],
        'C43' => ['name' => 'Camera 43 (South Highway)',  'zone' => 'Zone 4', 'resolution_weight' => 1.3, 'file' => 'camera_c43.mp4'],
        'C51' => ['name' => 'Camera 51 (Central Park)',   'zone' => 'Zone 5', 'resolution_weight' => 1.0, 'file' => 'camera_c51.mp4'],
        'C52' => ['name' => 'Camera 52 (Central Alley)',  'zone' => 'Zone 5', 'resolution_weight' => 0.95,'file' => 'camera_c52.mp4'],
        'C61' => ['name' => 'Camera 61 (Perimeter N)',    'zone' => 'Zone 6', 'resolution_weight' => 0.9, 'file' => 'camera_c61.mp4'],
        'C62' => ['name' => 'Camera 62 (Perimeter E)',    'zone' => 'Zone 6', 'resolution_weight' => 1.0, 'file' => 'camera_c62.mp4'],
        'C63' => ['name' => 'Camera 63 (Perimeter S)',    'zone' => 'Zone 6', 'resolution_weight' => 1.1, 'file' => 'camera_c63.mp4'],
        'C64' => ['name' => 'Camera 64 (Perimeter W)',    'zone' => 'Zone 6', 'resolution_weight' => 0.95,'file' => 'camera_c64.mp4'],
        'C65' => ['name' => 'Camera 65 (Perimeter C)',    'zone' => 'Zone 6', 'resolution_weight' => 1.0, 'file' => 'camera_c65.mp4'],
    ],

    'zones' => [
        'All Cameras (18)'  => ['C11','C12','C21','C22','C23','C24','C31','C32','C41','C42','C43','C51','C52','C61','C62','C63','C64','C65'],
        'Zone 1 (C11-C12)'  => ['C11', 'C12'],
        'Zone 2 (C21-C24)'  => ['C21', 'C22', 'C23', 'C24'],
        'Zone 3 (C31-C32)'  => ['C31', 'C32'],
        'Zone 4 (C41-C43)'  => ['C41', 'C42', 'C43'],
        'Zone 5 (C51-C52)'  => ['C51', 'C52'],
        'Zone 6 (C61-C65)'  => ['C61', 'C62', 'C63', 'C64', 'C65'],
    ],

    'thresholds' => [
        'confidence'       => 0.60, // Minimum confidence score for detection
        'hysteresis'       => 0.15, // Minimum score difference required for switching cameras
        'dbn_frame_buffer' => 5,    // Consecutive frames required before triggering switch
        'reid_similarity'  => 0.75, // Cosine/correlation similarity threshold for ReID match
        'max_disappeared'  => 30,   // Max frames a track can be missing before deregistration
        'max_distance'     => 80,   // Max centroid pixel distance for track assignment
        'fallback_frames'  => 3,    // Consecutive missed frames before auto fallback switch
    ],

    'smtp' => [
        'host'       => 'smtp.gmail.com',
        'port'       => 587,
        'username'   => 'surveillance.alerts@fastnuces.edu.pk',
        'password'   => 'app-specific-secret-key',
        'encryption' => 'tls',
        'from_email' => 'surveillance.alerts@fastnuces.edu.pk',
        'from_name'  => 'Vision Mixer AI System',
    ],

    'storage' => [
        'dataset_dir' => realpath(__DIR__ . '/../../../dataset') ?: (__DIR__ . '/../../../dataset'),
        'clips_dir'   => __DIR__ . '/../../storage/clips',
        'exports_dir' => __DIR__ . '/../../storage/exports',
        'ffmpeg_path' => 'ffmpeg',
    ]
];
