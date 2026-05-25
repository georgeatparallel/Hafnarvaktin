package is.fljotavik.backend.detection;

import java.time.Instant;
import java.util.List;

public record DetectionEventResponse(
        Integer id,
        Integer cameraId,
        Instant timestamp,
        List<LabelHit> labels
) {
    public record LabelHit(
            String name,
            Float confidence,
            Float bboxX,
            Float bboxY,
            Float bboxWidth,
            Float bboxHeight
    ) {
        public static LabelHit from(DetectionLabel dl) {
            return new LabelHit(
                    dl.getLabel().getName(),
                    dl.getConfidence(),
                    dl.getBboxX(),
                    dl.getBboxY(),
                    dl.getBboxWidth(),
                    dl.getBboxHeight()
            );
        }
    }

    public static DetectionEventResponse from(Detection d) {
        return new DetectionEventResponse(
                d.getId(),
                d.getCamera().getId(),
                d.getTimestamp(),
                d.getLabels().stream().map(LabelHit::from).toList()
        );
    }
}
