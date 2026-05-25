package is.fljotavik.backend.detection;

import is.fljotavik.backend.camera.Camera;
import is.fljotavik.backend.camera.CameraRepository;
import is.fljotavik.backend.inference.DetectionBox;
import is.fljotavik.backend.inference.DetectionEvent;
import is.fljotavik.backend.inference.InferenceEventBus;
import is.fljotavik.backend.label.Label;
import is.fljotavik.backend.label.LabelRepository;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Listens for raw per-frame detection events, collapses same-class runs on
 * the same camera into a single record, and persists them to Postgres. A
 * class is "ended" when no fresh detection of it arrives inside the
 * debounce window; the resulting row captures start time, peak confidence,
 * and the peak-confidence bounding box.
 *
 * <p>Raw events still flow onwards to the WebSocket bus — this service only
 * subscribes to the bus; it does not filter it.
 */
@Service
public class DetectionPersistenceService {

    private static final Logger log = LoggerFactory.getLogger(DetectionPersistenceService.class);

    private final InferenceEventBus bus;
    private final CameraRepository cameraRepository;
    private final LabelRepository labelRepository;
    private final DetectionRepository detectionRepository;
    private final Duration debounceWindow;

    private final Map<Key, Active> active = new ConcurrentHashMap<>();

    public DetectionPersistenceService(
            InferenceEventBus bus,
            CameraRepository cameraRepository,
            LabelRepository labelRepository,
            DetectionRepository detectionRepository,
            @Value("${fljotavik.detection.debounce-window-ms}") long debounceWindowMs
    ) {
        this.bus = bus;
        this.cameraRepository = cameraRepository;
        this.labelRepository = labelRepository;
        this.detectionRepository = detectionRepository;
        this.debounceWindow = Duration.ofMillis(debounceWindowMs);
    }

    @PostConstruct
    void register() {
        bus.subscribe(this::onEvent);
    }

    void onEvent(DetectionEvent event) {
        if (event == null || event.boxes() == null || event.boxes().isEmpty()) {
            return;
        }
        Instant ts = event.ts() != null ? event.ts() : Instant.now();
        if (event.cameraCode() != null && !event.cameraCode().isBlank()) {
            log.debug("onEvent camera_id={} camera_code={} model={} boxes={}",
                    event.cameraId(), event.cameraCode(), event.model(), event.boxes().size());
        } else {
            log.debug("onEvent camera_id={} model={} boxes={}",
                    event.cameraId(), event.model(), event.boxes().size());
        }
        for (DetectionBox box : event.boxes()) {
            Key key = new Key(event.cameraId(), box.cls());
            active.compute(key, (k, prev) -> {
                if (prev == null) {
                    return new Active(event.cameraId(), box.cls(), ts, ts, box.conf(), box);
                }
                prev.lastSeen = ts;
                if (box.conf() > prev.peakConf) {
                    prev.peakConf = box.conf();
                    prev.peakBox = box;
                }
                return prev;
            });
        }
    }

    @Scheduled(fixedDelayString = "${fljotavik.detection.flush-interval-ms}")
    public void flushExpired() {
        Instant cutoff = Instant.now().minus(debounceWindow);
        // Snapshot keys to avoid ConcurrentModificationException during removal.
        Map<Key, Active> expired = new HashMap<>();
        for (Map.Entry<Key, Active> entry : active.entrySet()) {
            if (entry.getValue().lastSeen.isBefore(cutoff)) {
                expired.put(entry.getKey(), entry.getValue());
            }
        }
        for (Key k : expired.keySet()) {
            Active removed = active.remove(k);
            if (removed != null) {
                try {
                    if (persist(removed)) {
                        log.debug("persisted detection camera={} cls={} peakConf={}",
                                removed.cameraId, removed.cls, removed.peakConf);
                    }
                } catch (RuntimeException ex) {
                    log.warn("Failed to persist detection for {}/{}: {}",
                            removed.cameraId, removed.cls, ex.getMessage());
                }
            }
        }
    }

    @Transactional
    boolean persist(Active a) {
        Camera camera = cameraRepository.findById(a.cameraId).orElse(null);
        if (camera == null) {
            log.debug("Skipping detection for unknown camera_id={}", a.cameraId);
            return false;
        }
        // Auto-create labels the first time the model emits them. The schema
        // seeds the core classes; best.pt can evolve to produce new ones
        // without a manual migration.
        Label label = labelRepository.findByName(a.cls)
                .orElseGet(() -> {
                    log.info("Creating new label row for class '{}'", a.cls);
                    return labelRepository.save(new Label(a.cls, null));
                });

        // thumbnail_path is NOT NULL in the schema, but this build persists
        // detection metadata only (no on-disk JPEG), so we store an empty string.
        Detection detection = new Detection(camera, a.start, "", null);

        List<Integer> xyxy = a.peakBox.xyxy();
        Float bx = null, by = null, bw = null, bh = null;
        if (xyxy != null && xyxy.size() == 4) {
            int x1 = xyxy.get(0);
            int y1 = xyxy.get(1);
            int x2 = xyxy.get(2);
            int y2 = xyxy.get(3);
            bx = (float) x1;
            by = (float) y1;
            bw = (float) (x2 - x1);
            bh = (float) (y2 - y1);
        }
        DetectionLabel dl = new DetectionLabel(label, a.peakConf, bx, by, bw, bh);
        detection.addLabel(dl);

        detectionRepository.save(detection);
        return true;
    }

    private record Key(Integer cameraId, String cls) {}

    private static final class Active {
        final Integer cameraId;
        final String cls;
        final Instant start;
        Instant lastSeen;
        float peakConf;
        DetectionBox peakBox;

        Active(Integer cameraId, String cls, Instant start, Instant lastSeen,
               float peakConf, DetectionBox peakBox) {
            this.cameraId = cameraId;
            this.cls = cls;
            this.start = start;
            this.lastSeen = lastSeen;
            this.peakConf = peakConf;
            this.peakBox = peakBox;
        }
    }
}
