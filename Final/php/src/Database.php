<?php
namespace VisionMixer;

use PDO;
use PDOException;

class Database {
    private static ?PDO $instance = null;
    private array $config;

    public function __construct(?array $config = null) {
        if ($config === null) {
            $config = require __DIR__ . '/../config/config.php';
        }
        $this->config = $config['database'];
    }

    public function getConnection(): PDO {
        if (self::$instance === null) {
            $dbPath = $this->config['path'];
            $dbDir = dirname($dbPath);
            if (!is_dir($dbDir)) {
                mkdir($dbDir, 0777, true);
            }

            try {
                self::$instance = new PDO("sqlite:" . $dbPath);
                self::$instance->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
                self::$instance->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
                $this->migrate();
            } catch (PDOException $e) {
                throw new \RuntimeException("Database Connection Error: " . $e->getMessage());
            }
        }
        return self::$instance;
    }

    public function migrate(): void {
        $db = self::$instance;

        $queries = [
            // Cameras table
            "CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                camera_name TEXT NOT NULL,
                zone TEXT NOT NULL,
                resolution_weight REAL NOT NULL DEFAULT 1.0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )",

            // Vehicles (Global ID) table
            "CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id TEXT PRIMARY KEY, -- e.g. VH-001
                global_track_id INTEGER UNIQUE,
                color TEXT,
                plate_number TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )",

            // Tracks table (local tracks per camera)
            "CREATE TABLE IF NOT EXISTS tracks (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                bbox_data TEXT, -- JSON coordinates
                FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            )",

            // Clips table
            "CREATE TABLE IF NOT EXISTS clips (
                clip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                track_id INTEGER,
                vehicle_id TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                file_path TEXT NOT NULL,
                resolution TEXT DEFAULT '1080p',
                FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            )",

            // Feature Embeddings table
            "CREATE TABLE IF NOT EXISTS feature_embeddings (
                embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id TEXT NOT NULL,
                track_id INTEGER,
                feature_vector TEXT NOT NULL, -- JSON array of histogram / embedding values
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            )",

            // Video Requests table
            "CREATE TABLE IF NOT EXISTS video_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id TEXT NOT NULL,
                request_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent_time DATETIME,
                recipient_email TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
                video_path TEXT,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
            )",

            // Notifications table
            "CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                sent_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                video_path TEXT,
                status TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES video_requests(request_id)
            )"
        ];

        foreach ($queries as $query) {
            $db->exec($query);
        }

        // Seed default cameras if table is empty
        $stmt = $db->query("SELECT COUNT(*) as count FROM cameras");
        if ($stmt->fetch()['count'] == 0) {
            $config = require __DIR__ . '/../config/config.php';
            $insert = $db->prepare("INSERT INTO cameras (camera_id, camera_name, zone, resolution_weight) VALUES (?, ?, ?, ?)");
            foreach ($config['cameras'] as $id => $info) {
                $insert->execute([$id, $info['name'], $info['zone'], $info['resolution_weight']]);
            }
        }
    }
}
