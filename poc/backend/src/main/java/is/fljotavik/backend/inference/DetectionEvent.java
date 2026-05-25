package is.fljotavik.backend.inference;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.List;

/**
 * JSON payload emitted by the Python inference service over SSE at
 * {@code GET /detections}. Shape: {@code {ts, camera_id, camera_code, model, boxes}}.
 *
 * <p>{@code camera_id} is the numeric DB primary key (cameras.id) used for
 * persistence; {@code camera_code} is the short directional code ("N", "S")
 * surfaced in human-facing logs. Jackson tolerates camera_code being absent
 * (older inference deployments) — null is acceptable.
 */
public record DetectionEvent(
        Instant ts,
        @JsonProperty("camera_id") Integer cameraId,
        @JsonProperty("camera_code") String cameraCode,
        String model,
        List<DetectionBox> boxes
) {
}
