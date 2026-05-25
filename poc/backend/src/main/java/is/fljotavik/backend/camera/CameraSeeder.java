package is.fljotavik.backend.camera;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * Upserts camera rows from the CAMERAS_JSON env var at startup so
 * detection persistence (which FK-references cameras.id) doesn't fail
 * for multi-camera deployments. Schema seeding via seed-camera.sh only
 * runs on the first DB init — this runner keeps things in sync after.
 *
 * CAMERAS_JSON format:
 *   [{"id": 1, "name": "Perlan · south", "url": "https://..."}, ...]
 *
 * When the env is empty or malformed, this runner is a no-op.
 */
@Component
public class CameraSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(CameraSeeder.class);

    private final JdbcTemplate jdbc;
    private final String camerasJson;
    private final ObjectMapper mapper = new ObjectMapper();

    public CameraSeeder(JdbcTemplate jdbc, @Value("${CAMERAS_JSON:}") String camerasJson) {
        this.jdbc = jdbc;
        this.camerasJson = camerasJson == null ? "" : camerasJson.trim();
    }

    @Override
    public void run(ApplicationArguments args) {
        if (camerasJson.isEmpty()) {
            log.info("CameraSeeder: CAMERAS_JSON empty — nothing to seed");
            return;
        }

        List<Map<String, Object>> entries;
        try {
            entries = mapper.readValue(camerasJson, new TypeReference<>() {});
        } catch (Exception ex) {
            log.warn("CameraSeeder: CAMERAS_JSON parse failed — skipping", ex);
            return;
        }

        for (Map<String, Object> entry : entries) {
            Integer id = toInt(entry.get("id"));
            String name = String.valueOf(entry.getOrDefault("name", "Camera " + id));
            String url  = String.valueOf(entry.getOrDefault("url", ""));
            String location = String.valueOf(entry.getOrDefault("location", "Reykjavík"));
            if (id == null) {
                log.warn("CameraSeeder: entry missing id — {}", entry);
                continue;
            }
            jdbc.update(
                    """
                    INSERT INTO cameras (id, name, location, rtsp_url)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE
                      SET name = EXCLUDED.name,
                          location = EXCLUDED.location,
                          rtsp_url = EXCLUDED.rtsp_url
                    """,
                    id, name, location, url
            );
        }
        // Resync the SERIAL sequence so future inserts without an explicit
        // id don't collide with our seeded ids. setval() is a SELECT that
        // returns the new sequence value, so use queryForObject, not update().
        jdbc.queryForObject(
                "SELECT setval(pg_get_serial_sequence('cameras','id'), (SELECT COALESCE(MAX(id),1) FROM cameras))",
                Long.class);
        log.info("CameraSeeder: upserted {} camera row(s)", entries.size());
    }

    private static Integer toInt(Object raw) {
        if (raw instanceof Number n) return n.intValue();
        if (raw instanceof String s) {
            try { return Integer.parseInt(s); } catch (NumberFormatException ignored) { return null; }
        }
        return null;
    }
}
