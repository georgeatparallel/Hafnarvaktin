package is.fljotavik.backend.detection;

import is.fljotavik.backend.camera.Camera;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "detections")
public class Detection {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "camera_id", nullable = false)
    private Camera camera;

    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;

    @Column(name = "thumbnail_path", nullable = false, columnDefinition = "TEXT")
    private String thumbnailPath;

    @Column(name = "processing_time_ms")
    private Integer processingTimeMs;

    @OneToMany(mappedBy = "detection", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<DetectionLabel> labels = new ArrayList<>();

    protected Detection() {
        // for JPA
    }

    public Detection(Camera camera, Instant timestamp, String thumbnailPath, Integer processingTimeMs) {
        this.camera = camera;
        this.timestamp = timestamp;
        this.thumbnailPath = thumbnailPath;
        this.processingTimeMs = processingTimeMs;
    }

    public void addLabel(DetectionLabel label) {
        labels.add(label);
        label.setDetection(this);
    }

    public Integer getId() {
        return id;
    }

    public Camera getCamera() {
        return camera;
    }

    public Instant getTimestamp() {
        return timestamp;
    }

    public String getThumbnailPath() {
        return thumbnailPath;
    }

    public Integer getProcessingTimeMs() {
        return processingTimeMs;
    }

    public List<DetectionLabel> getLabels() {
        return List.copyOf(labels);
    }
}
