package is.fljotavik.backend.detection;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/api/v1/events")
public class DetectionQueryController {

    private static final int DEFAULT_PAGE_SIZE = 50;
    private static final int MAX_PAGE_SIZE = 200;

    private final DetectionRepository detectionRepository;

    public DetectionQueryController(DetectionRepository detectionRepository) {
        this.detectionRepository = detectionRepository;
    }

    @GetMapping
    @Transactional(readOnly = true)
    public EventsPage list(
            @RequestParam(name = "from", required = false) Instant from,
            @RequestParam(name = "to", required = false) Instant to,
            @RequestParam(name = "class", required = false) String cls,
            @RequestParam(name = "page", defaultValue = "0") int page,
            @RequestParam(name = "size", defaultValue = "50") int size
    ) {
        Instant toBound = to != null ? to : Instant.now();
        Instant fromBound = from != null ? from : toBound.minus(Duration.ofDays(1));
        int safeSize = Math.min(Math.max(size, 1), MAX_PAGE_SIZE);
        int safePage = Math.max(page, 0);

        Page<Detection> results = detectionRepository.search(
                fromBound, toBound, cls, PageRequest.of(safePage, safeSize));
        List<DetectionEventResponse> content = results.getContent().stream()
                .map(DetectionEventResponse::from)
                .toList();
        return new EventsPage(
                content,
                safePage,
                safeSize,
                results.getTotalElements(),
                results.getTotalPages(),
                fromBound,
                toBound,
                cls
        );
    }

    public record EventsPage(
            List<DetectionEventResponse> content,
            int page,
            int size,
            long totalElements,
            int totalPages,
            Instant from,
            Instant to,
            String appliedClass
    ) {
    }
}
