package is.fljotavik.backend.detection;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;

public interface DetectionRepository extends JpaRepository<Detection, Integer> {

    @Query("""
           SELECT d FROM Detection d
           WHERE d.timestamp >= :from
             AND d.timestamp < :to
             AND (:cls IS NULL
                  OR EXISTS (SELECT 1 FROM DetectionLabel dl
                             WHERE dl.detection = d AND dl.label.name = :cls))
           ORDER BY d.timestamp DESC
           """)
    Page<Detection> search(
            @Param("from") Instant from,
            @Param("to") Instant to,
            @Param("cls") String cls,
            Pageable pageable);

    @Query("""
           SELECT COUNT(d) FROM Detection d
           WHERE d.timestamp >= :from AND d.timestamp < :to
           """)
    long countInRange(@Param("from") Instant from, @Param("to") Instant to);

    @Query("""
           SELECT dl.label.name AS name, COUNT(dl) AS count
           FROM DetectionLabel dl
           WHERE dl.detection.timestamp >= :from AND dl.detection.timestamp < :to
           GROUP BY dl.label.name
           ORDER BY COUNT(dl) DESC
           """)
    List<ClassCount> classHistogram(@Param("from") Instant from, @Param("to") Instant to);

    @Query("""
           SELECT dl.label.name AS name, MAX(dl.detection.timestamp) AS lastSeen
           FROM DetectionLabel dl
           GROUP BY dl.label.name
           """)
    List<ClassLastSeen> lastSeenByClass();

    interface ClassCount {
        String getName();
        long getCount();
    }

    interface ClassLastSeen {
        String getName();
        Instant getLastSeen();
    }
}
