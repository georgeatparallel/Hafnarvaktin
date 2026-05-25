package is.fljotavik.backend.detection;

import is.fljotavik.backend.label.Label;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "detection_labels")
public class DetectionLabel {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "detection_id", nullable = false)
    private Detection detection;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "label_id", nullable = false)
    private Label label;

    @Column(nullable = false)
    private Float confidence;

    @Column(name = "bbox_x")
    private Float bboxX;

    @Column(name = "bbox_y")
    private Float bboxY;

    @Column(name = "bbox_width")
    private Float bboxWidth;

    @Column(name = "bbox_height")
    private Float bboxHeight;

    protected DetectionLabel() {
        // for JPA
    }

    public DetectionLabel(Label label, float confidence, Float bboxX, Float bboxY, Float bboxWidth, Float bboxHeight) {
        this.label = label;
        this.confidence = confidence;
        this.bboxX = bboxX;
        this.bboxY = bboxY;
        this.bboxWidth = bboxWidth;
        this.bboxHeight = bboxHeight;
    }

    void setDetection(Detection detection) {
        this.detection = detection;
    }

    public Integer getId() {
        return id;
    }

    public Detection getDetection() {
        return detection;
    }

    public Label getLabel() {
        return label;
    }

    public Float getConfidence() {
        return confidence;
    }

    public Float getBboxX() {
        return bboxX;
    }

    public Float getBboxY() {
        return bboxY;
    }

    public Float getBboxWidth() {
        return bboxWidth;
    }

    public Float getBboxHeight() {
        return bboxHeight;
    }
}
