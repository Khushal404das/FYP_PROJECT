<?php
/**
 * config.php — global configuration for the FYP Vehicle Tracking System
 */

define('PYTHON_API_BASE', 'http://127.0.0.1:5000/api');
define('UPLOAD_DIR',      __DIR__ . '/uploads/');
define('MAX_FILE_SIZE',   50 * 1024 * 1024);  // 50 MB
define('APP_NAME',        'FYP Vehicle Tracking System');
define('APP_VERSION',     '1.0.0');

// Camera info (mirrors Python config)
define('CAMERAS', json_encode([
    'c11','c12','c21','c22','c23','c24',
    'c31','c32','c41','c42','c43',
    'c51','c52','c61','c62','c63','c64','c65',
]));

/**
 * Make a request to the Python API.
 *
 * @param string $endpoint  e.g. '/query_image'
 * @param string $method    GET|POST
 * @param array  $data      POST body fields
 * @param array  $files     ['field_name' => '/path/to/file']
 * @return array
 */
function api_request(string $endpoint, string $method = 'GET', array $data = [], array $files = []): array {
    $url = PYTHON_API_BASE . $endpoint;
    $ch  = curl_init($url);

    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 120);

    if (strtoupper($method) === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);

        if (!empty($files)) {
            // multipart/form-data
            $postFields = $data;
            foreach ($files as $field => $path) {
                $postFields[$field] = new CURLFile($path);
            }
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postFields);
        } else {
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
            curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        }
    }

    $raw  = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);

    if ($raw === false || !empty($err)) {
        return ['success' => false, 'error' => 'API connection failed: ' . $err, 'http_code' => 0];
    }

    $decoded = json_decode($raw, true);
    if ($decoded === null) {
        return ['success' => false, 'error' => 'Invalid JSON from API', 'raw' => $raw, 'http_code' => $code];
    }

    $decoded['http_code'] = $code;
    return $decoded;
}

/**
 * Format a Unix timestamp to human-readable string.
 */
function fmt_time(float $ts): string {
    if ($ts <= 0) return '—';
    // Treat timestamp as seconds-in-video
    $m = intdiv((int)$ts, 60);
    $s = (int)$ts % 60;
    return sprintf('%02d:%02d', $m, $s);
}

/**
 * Return a badge HTML for a camera ID.
 */
function cam_badge(string $cam): string {
    return '<span class="cam-badge cam-' . htmlspecialchars($cam) . '">'
         . htmlspecialchars(strtoupper($cam)) . '</span>';
}
