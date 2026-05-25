package is.fljotavik.backend.inference;

import java.util.List;

/**
 * One bounding box inside a detection event coming from the inference
 * service. xyxy is [x1, y1, x2, y2] in pixel coordinates.
 */
public record DetectionBox(String cls, float conf, List<Integer> xyxy) {
}
