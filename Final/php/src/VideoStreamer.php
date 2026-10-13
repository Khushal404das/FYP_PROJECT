<?php
namespace VisionMixer;

/**
 * VideoStreamer
 * High-performance HTTP 206 Partial Content Range streaming engine for CCTV video files.
 * Allows browsers to play and seek large CCTV videos smoothly with low memory usage.
 */
class VideoStreamer {
    private string $filePath;
    private int $fileSize;
    private $stream = null;
    private int $start = 0;
    private int $end = 0;

    public function __construct(string $filePath) {
        if (!file_exists($filePath) || !is_readable($filePath)) {
            throw new \InvalidArgumentException("Video file not found or unreadable: " . basename($filePath));
        }

        $this->filePath = $filePath;
        $this->fileSize = (int)filesize($filePath);
    }

    /**
     * Streams the requested byte range or full video to client
     */
    public function stream(): void {
        $this->stream = fopen($this->filePath, 'rb');
        if ($this->stream === false) {
            http_response_code(500);
            echo "Failed to open video file";
            return;
        }

        $this->start = 0;
        $this->end   = $this->fileSize - 1;

        // Clean any output buffers
        while (ob_get_level()) {
            ob_end_clean();
        }

        header('Content-Type: video/mp4');
        header('Accept-Ranges: bytes');
        header('Cache-Control: public, max-age=3600');

        if (isset($_SERVER['HTTP_RANGE'])) {
            $this->handleRangeHeader();
        } else {
            header("Content-Length: {$this->fileSize}");
        }

        // Seek and output chunk
        fseek($this->stream, $this->start);
        $bufferSize = 1024 * 64; // 64KB buffer
        $bytesRemaining = $this->end - $this->start + 1;

        while (!feof($this->stream) && $bytesRemaining > 0 && connection_status() === 0) {
            $bytesToRead = min($bufferSize, $bytesRemaining);
            $data = fread($this->stream, $bytesToRead);
            if ($data === false) break;
            echo $data;
            flush();
            $bytesRemaining -= strlen($data);
        }

        fclose($this->stream);
    }

    private function handleRangeHeader(): void {
        $range = $_SERVER['HTTP_RANGE'];
        if (preg_match('/bytes=(\d+)-(\d*)/', $range, $matches)) {
            $this->start = (int)$matches[1];
            if (!empty($matches[2])) {
                $this->end = (int)$matches[2];
            }
        }

        // Sanity boundary checks
        if ($this->start > $this->end || $this->start >= $this->fileSize) {
            http_response_code(416); // Range Not Satisfiable
            header("Content-Range: bytes */{$this->fileSize}");
            exit;
        }

        $this->end = min($this->end, $this->fileSize - 1);
        $contentLength = $this->end - $this->start + 1;

        http_response_code(206);
        header("Content-Length: {$contentLength}");
        header("Content-Range: bytes {$this->start}-{$this->end}/{$this->fileSize}");
    }
}
