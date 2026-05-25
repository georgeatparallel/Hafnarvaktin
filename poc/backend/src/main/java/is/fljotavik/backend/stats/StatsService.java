package is.fljotavik.backend.stats;

import is.fljotavik.backend.detection.DetectionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;

@Service
public class StatsService {

    private static final Duration DEFAULT_WINDOW = Duration.ofHours(24);

    private final DetectionRepository detectionRepository;

    public StatsService(DetectionRepository detectionRepository) {
        this.detectionRepository = detectionRepository;
    }

    @Transactional(readOnly = true)
    public StatsSummary summary() {
        Instant to = Instant.now();
        Instant from = to.minus(DEFAULT_WINDOW);
        long total = detectionRepository.countInRange(from, to);
        double hours = DEFAULT_WINDOW.toMinutes() / 60.0;
        double perHour = hours > 0 ? total / hours : 0;

        var histogram = detectionRepository.classHistogram(from, to).stream()
                .map(row -> new StatsSummary.ClassBucket(row.getName(), row.getCount()))
                .toList();
        var lastSeen = detectionRepository.lastSeenByClass().stream()
                .map(row -> new StatsSummary.ClassLastSeen(row.getName(), row.getLastSeen()))
                .toList();

        return new StatsSummary(from, to, total, perHour, histogram, lastSeen);
    }
}
