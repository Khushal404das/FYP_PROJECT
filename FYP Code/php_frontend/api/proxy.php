<?php
/**
 * api/proxy.php — PHP-side AJAX proxy for the Python Flask API
 * =============================================================
 * The JS frontend can call this instead of hitting Flask directly
 * when CORS is restricted.
 *
 * Usage (from JS):
 *   fetch('api/proxy.php?endpoint=/summary')
 *   fetch('api/proxy.php?endpoint=/journey/3')
 *   fetch('api/proxy.php', { method:'POST', body: formData })   ← for uploads
 */

require_once __DIR__ . '/../config.php';

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$endpoint = trim($_GET['endpoint'] ?? '');
if (empty($endpoint)) {
    echo json_encode(['success' => false, 'error' => 'Missing endpoint parameter']);
    exit;
}

// Sanitise endpoint
$endpoint = '/' . ltrim(preg_replace('/[^a-zA-Z0-9\/_.=-]/', '', $endpoint), '/');

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $result = api_request($endpoint, 'GET');
} else {
    // POST — check for file uploads
    $files = [];
    foreach ($_FILES as $field => $file) {
        if ($file['error'] === UPLOAD_ERR_OK) {
            $files[$field] = $file['tmp_name'];
        }
    }
    $data = array_merge($_POST, []);
    $result = api_request($endpoint, 'POST', $data, $files);
}

echo json_encode($result);
