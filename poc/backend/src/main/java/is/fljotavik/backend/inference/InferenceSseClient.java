package is.fljotavik.backend.inference;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Subscribes to the inference service's SSE stream at
 * {@code GET /detections} and republishes every event onto the in-process
 * {@link InferenceEventBus}. Runs on its own daemon thread with exponential
 * backoff on connection failure — the JVM never blocks on inference.
 */
@Component
public class InferenceSseClient {

    private static final Logger log = LoggerFactory.getLogger(InferenceSseClient.class);

    private final InferenceEventBus bus;
    private final ObjectMapper mapper;
    private final HttpClient httpClient;
    private final URI detectionsUri;
    private volatile boolean running;
    private Thread worker;

    public InferenceSseClient(
            InferenceEventBus bus,
            ObjectMapper mapper,
            @Value("${fljotavik.inference.base-url}") String baseUrl
    ) {
        this.bus = bus;
        this.mapper = mapper;
        this.detectionsUri = URI.create(baseUrl.replaceAll("/+$", "") + "/detections");
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    @PostConstruct
    public void start() {
        running = true;
        worker = new Thread(this::runForever, "inference-sse-client");
        worker.setDaemon(true);
        worker.start();
    }

    @PreDestroy
    public void stop() {
        running = false;
        if (worker != null) {
            worker.interrupt();
        }
    }

    private void runForever() {
        long backoffMs = 1000L;
        final long backoffMaxMs = 30_000L;

        while (running) {
            try {
                streamOnce();
                backoffMs = 1000L;
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception ex) {
                log.warn("Inference SSE connection dropped ({}). Reconnecting in {}ms",
                        ex.getMessage(), backoffMs);
                try {
                    Thread.sleep(backoffMs);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return;
                }
                backoffMs = Math.min(backoffMs * 2, backoffMaxMs);
            }
        }
    }

    private void streamOnce() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder(detectionsUri)
                .timeout(Duration.ofHours(24))
                .header("Accept", "text/event-stream")
                .GET()
                .build();

        HttpResponse<java.io.InputStream> response =
                httpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());

        if (response.statusCode() != 200) {
            throw new IOException("SSE connect returned " + response.statusCode());
        }

        log.info("Connected to inference SSE at {}", detectionsUri);

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
            StringBuilder data = new StringBuilder();
            String line;
            while (running && (line = reader.readLine()) != null) {
                if (line.isEmpty()) {
                    if (data.length() > 0) {
                        dispatch(data.toString());
                        data.setLength(0);
                    }
                    continue;
                }
                if (line.startsWith(":")) {
                    continue; // keepalive comment
                }
                if (line.startsWith("data:")) {
                    String payload = line.substring(5).stripLeading();
                    if (data.length() > 0) {
                        data.append('\n');
                    }
                    data.append(payload);
                }
            }
        }
    }

    private void dispatch(String json) {
        try {
            DetectionEvent event = mapper.readValue(json, DetectionEvent.class);
            bus.publish(event);
        } catch (Exception ex) {
            log.warn("Ignoring malformed detection event: {}", ex.getMessage());
        }
    }
}
