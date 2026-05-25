package is.fljotavik.backend.inference;

import is.fljotavik.backend.camera.CameraRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

@RestController
@RequestMapping("/api/v1/cameras")
public class SnapshotController {

    private final CameraRepository cameraRepository;
    private final HttpClient snapshotClient;
    private final HttpClient streamClient;
    private final String inferenceBase;

    public SnapshotController(
            CameraRepository cameraRepository,
            @Value("${fljotavik.inference.base-url}") String baseUrl
    ) {
        this.cameraRepository = cameraRepository;
        this.inferenceBase = baseUrl.replaceAll("/+$", "");
        // Short timeout for one-shot snapshots.
        this.snapshotClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))
                .build();
        // Dedicated long-lived client for the MJPEG proxy — no response
        // timeout so the multipart stream can stay open indefinitely.
        this.streamClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    @GetMapping("/{id}/snapshot")
    public ResponseEntity<byte[]> snapshot(@PathVariable Integer id) {
        if (cameraRepository.findById(id).isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        URI target = URI.create(inferenceBase + "/cameras/" + id + "/snapshot.jpg");
        HttpRequest request = HttpRequest.newBuilder(target)
                .timeout(Duration.ofSeconds(5))
                .GET()
                .build();

        HttpResponse<byte[]> response;
        try {
            response = snapshotClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
        } catch (IOException ex) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        }

        if (response.statusCode() != 200) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        }

        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_JPEG)
                .cacheControl(org.springframework.http.CacheControl.noStore())
                .body(response.body());
    }

    /**
     * Transparent pass-through of the inference service's MJPEG stream.
     * Keeps the browser on the backend origin (port 8091) instead of
     * talking to port 8084 directly. The body is streamed chunk-for-chunk
     * with no buffering so motion stays real-time.
     */
    @GetMapping("/{id}/stream.mjpg")
    public ResponseEntity<StreamingResponseBody> stream(@PathVariable Integer id) {
        if (cameraRepository.findById(id).isEmpty()) {
            return ResponseEntity.notFound().build();
        }

        URI target = URI.create(inferenceBase + "/cameras/" + id + "/stream.mjpg");
        HttpRequest request = HttpRequest.newBuilder(target)
                .GET()
                .build();

        HttpResponse<InputStream> response;
        try {
            response = streamClient.send(request, HttpResponse.BodyHandlers.ofInputStream());
        } catch (IOException ex) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        }

        if (response.statusCode() != 200) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).build();
        }

        String contentType = response.headers().firstValue("content-type")
                .orElse("multipart/x-mixed-replace; boundary=frame");

        StreamingResponseBody body = out -> {
            try (InputStream in = response.body()) {
                byte[] buf = new byte[16 * 1024];
                int n;
                while ((n = in.read(buf)) != -1) {
                    out.write(buf, 0, n);
                    out.flush();
                }
            } catch (IOException ignored) {
                // Client disconnected — normal for long-lived streams.
            }
        };

        return ResponseEntity.ok()
                .header("Content-Type", contentType)
                .header("Cache-Control", "no-store, no-cache, no-transform")
                .header("X-Accel-Buffering", "no")
                .body(body);
    }
}
