package is.fljotavik.backend.inference;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

/**
 * In-process fan-out for detection events coming off the inference SSE
 * stream. The SSE client publishes; subscribers (WebSocket handler,
 * persistence service) consume. Subscriber exceptions never stop the bus.
 */
@Component
public class InferenceEventBus {

    private static final Logger log = LoggerFactory.getLogger(InferenceEventBus.class);

    private final List<Consumer<DetectionEvent>> subscribers = new CopyOnWriteArrayList<>();

    public void subscribe(Consumer<DetectionEvent> handler) {
        subscribers.add(handler);
    }

    public void publish(DetectionEvent event) {
        for (Consumer<DetectionEvent> handler : subscribers) {
            try {
                handler.accept(event);
            } catch (RuntimeException ex) {
                log.warn("Subscriber threw while handling detection event", ex);
            }
        }
    }
}
