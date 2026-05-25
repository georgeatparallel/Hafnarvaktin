package is.fljotavik.backend.stats;

import java.time.Instant;
import java.util.List;

public record StatsSummary(
        Instant from,
        Instant to,
        long detectionsInWindow,
        double detectionsPerHour,
        List<ClassBucket> classHistogram,
        List<ClassLastSeen> lastSeenByClass
) {
    public record ClassBucket(String name, long count) {}
    public record ClassLastSeen(String name, Instant lastSeen) {}
}
