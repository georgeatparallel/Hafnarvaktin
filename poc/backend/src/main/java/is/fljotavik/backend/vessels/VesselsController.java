package is.fljotavik.backend.vessels;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Vessel endpoints for the Hafnarvaktin RN app.
 *
 *   GET /api/v1/vessels/status        — Fleet tab. "In port" / "at sea" lists,
 *                                       live AIS positions enriched with the
 *                                       Samgöngustofa registry (proper accented
 *                                       names, skipaskrárnúmer, type, length,
 *                                       home port).
 *   GET /api/v1/vessels/live          — Raw cached AIS list (Datalastic shape),
 *                                       consumed by the MCP server. A single 60 s
 *                                       cached snapshot keeps the numbers consistent
 *                                       and Datalastic free-tier usage low.
 *
 * Live picture: Datalastic vessel_inradius (AIS). One snapshot at
 * {@link #DEFAULT_RADIUS_KM} km is cached for {@link #CACHE_TTL}; /status and
 * /live both serve it, which keeps Datalastic free-tier usage low and keeps the
 * Fleet tab consistent. If the key is missing or the call
 * fails, /status falls back to a deterministic split of the Westfjords-home-ported
 * registry vessels.
 *
 * Static facts (accented name, type, length, home port) come from the
 * {@code vessels} table mirrored from Samgöngustofa — AIS static data is
 * unreliable for Icelandic coastal vessels. Live vessels are matched to the
 * registry in three steps: by MMSI first; then (since Samgöngustofa does not
 * publish MMSI, so most rows have NULL mmsi) by accent-folded name within the
 * local Westfjords fleet; then by the umdæmismerking embedded in the AIS name
 * (e.g. "BLIKI IS 414" → ÍS-414). The two fallbacks only resolve on a unique
 * local match, so a vessel is never shown a wrong skipaskrárnúmer.
 */
@RestController
@RequestMapping("/api/v1/vessels")
public class VesselsController {

    private static final int DEFAULT_RADIUS_KM = 10;
    private static final double IN_PORT_SPEED_KN = 0.5;
    private static final int MAX_PER_SIDE = 80;
    private static final Duration CACHE_TTL = Duration.ofSeconds(60);

    // Westfjords home-port spellings — registry fallback only.
    private static final String LOCAL_PORTS_SQL = """
            home_port ILIKE '%safj%'
            OR home_port ILIKE '%bolungarv%'
            OR home_port ILIKE '%suðurey%'
            OR home_port ILIKE '%sudurey%'
            OR home_port ILIKE '%flatey%'
            OR home_port ILIKE '%þingeyr%'
            OR home_port ILIKE '%thingeyr%'
            OR home_port ILIKE '%patreks%'
            OR home_port ILIKE '%hnífsdal%'
            OR home_port ILIKE '%hnifsdal%'
            """;

    private final JdbcTemplate jdbc;
    private final RestClient http;
    private final String datalasticKey;
    private final double harbourLat;
    private final double harbourLon;

    /** Cached raw Datalastic vessel list at DEFAULT_RADIUS_KM. */
    private volatile List<Map<String, Object>> cachedRaw;
    private volatile Instant cachedAt = Instant.EPOCH;

    public VesselsController(
            JdbcTemplate jdbc,
            @Value("${datalastic.api-key:}") String datalasticKey,
            @Value("${harbour.lat:66.07}") double harbourLat,
            @Value("${harbour.lon:-23.13}") double harbourLon) {
        this.jdbc = jdbc;
        this.http = RestClient.builder().build();
        this.datalasticKey = datalasticKey;
        this.harbourLat = harbourLat;
        this.harbourLon = harbourLon;
    }

    // ── /live — raw cached AIS list (Datalastic shape) ───────────────────────

    @GetMapping("/live")
    public Map<String, Object> live(@RequestParam(name = "radius", required = false) Integer radius) {
        int r = radius == null ? DEFAULT_RADIUS_KM : radius;
        List<Map<String, Object>> vessels = (r == DEFAULT_RADIUS_KM) ? snapshot() : fetchDatalastic(r);
        return Map.of(
                "data", Map.of("vessels", vessels == null ? List.of() : vessels),
                "meta", Map.of(
                        "radius_km", r,
                        "source", "hafnarvaktin-cache",
                        "snapshot_at", cachedAt.toString(),
                        "count", vessels == null ? 0 : vessels.size()));
    }

    // ── /status — Fleet tab ─────────────────────────────────────────────────

    @GetMapping("/status")
    public StatusResponse status() {
        List<Map<String, Object>> raw = (datalasticKey == null || datalasticKey.isBlank()) ? null : snapshot();
        if (raw == null) return registryFallback();

        Set<Long> mmsis = new LinkedHashSet<>();
        for (Map<String, Object> v : raw) {
            Long m = asLong(v.get("mmsi"));
            if (m != null) mmsis.add(m);
        }
        Map<Long, RegRow> reg = loadRegistryByMmsi(mmsis);
        LocalRegistry local = loadLocalRegistry();

        List<VesselRow> inPort = new ArrayList<>();
        List<VesselRow> atSea = new ArrayList<>();
        for (Map<String, Object> v : raw) {
            VesselRow row = enrich(v, reg, local);
            double spd = asDouble(v.get("speed"));
            if (spd < IN_PORT_SPEED_KN) {
                if (inPort.size() < MAX_PER_SIDE) inPort.add(row);
            } else {
                if (atSea.size() < MAX_PER_SIDE) atSea.add(row);
            }
        }
        return new StatusResponse(inPort, atSea, "datalastic+registry", cachedAt.toString());
    }

    private VesselRow enrich(Map<String, Object> v, Map<Long, RegRow> reg, LocalRegistry local) {
        Long mmsi = asLong(v.get("mmsi"));
        String imo = strOrNull(v.get("imo"));
        Double speed = v.get("speed") == null ? null : asDouble(v.get("speed"));
        String destination = strOrNull(v.get("destination"));
        String aisName = strOrNull(v.get("name"));
        String aisType = v.get("type_specific") != null ? v.get("type_specific").toString()
                : (v.get("type") != null ? v.get("type").toString() : null);
        Float aisLen = asFloat(v.get("length"));

        // 1) MMSI is the strongest key, but Samgöngustofa doesn't publish it, so it
        //    only matches a minority. 2) fall back to the accent-folded name within
        //    the local fleet, 3) then to the umdæmismerking embedded in the AIS name
        //    (e.g. "BLIKI IS 414" → ÍS-414). Both fallbacks only hit on a UNIQUE
        //    local match, so we never show a wrong skipaskrárnúmer.
        RegRow rr = mmsi == null ? null : reg.get(mmsi);
        if (rr == null && aisName != null) {
            rr = local.byName().get(foldName(aisName));
            if (rr == null) {
                String mark = markFromAisName(aisName);
                if (mark != null) rr = local.byMark().get(mark);
            }
        }
        if (rr != null) {
            String label = (rr.regno() != null && !rr.regno().isBlank())
                    ? rr.name() + " (IS-" + rr.regno() + ")"
                    : rr.name();
            return new VesselRow(
                    rr.name(),
                    label,
                    rr.regno(),
                    rr.type() != null ? rr.type() : aisType,
                    rr.lengthM() != null ? rr.lengthM() : aisLen,
                    rr.homePort(),
                    speed,
                    mmsi,
                    imo,
                    destination,
                    true);
        }
        String name = aisName != null ? aisName : "(unnamed)";
        return new VesselRow(name, name, null, aisType, aisLen, null, speed, mmsi, imo, destination, false);
    }

    // ── Datalastic + cache ──────────────────────────────────────────────────

    /** Returns the cached raw vessel list at the default radius, refreshing if stale. */
    private List<Map<String, Object>> snapshot() {
        if (cachedRaw != null && Duration.between(cachedAt, Instant.now()).compareTo(CACHE_TTL) < 0) {
            return cachedRaw;
        }
        List<Map<String, Object>> fresh = fetchDatalastic(DEFAULT_RADIUS_KM);
        if (fresh != null) {
            cachedRaw = fresh;
            cachedAt = Instant.now();
        }
        return cachedRaw; // may be null on the very first failure
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> fetchDatalastic(int radiusKm) {
        if (datalasticKey == null || datalasticKey.isBlank()) return null;
        try {
            Map<String, Object> resp = http.get()
                    .uri("https://api.datalastic.com/api/v0/vessel_inradius?api-key={k}&lat={lat}&lon={lon}&radius={r}",
                            datalasticKey, harbourLat, harbourLon, radiusKm)
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(Map.class);
            if (resp == null) return null;
            Map<String, Object> data = (Map<String, Object>) resp.get("data");
            if (data == null) return null;
            return (List<Map<String, Object>>) data.get("vessels");
        } catch (Exception e) {
            return null;
        }
    }

    // ── Registry lookups ────────────────────────────────────────────────────

    private Map<Long, RegRow> loadRegistryByMmsi(Set<Long> mmsis) {
        Map<Long, RegRow> out = new HashMap<>();
        if (mmsis.isEmpty()) return out;
        String placeholders = String.join(",", java.util.Collections.nCopies(mmsis.size(), "?"));
        jdbc.query(
                "SELECT mmsi, registration_no, name, type, length_m, home_port FROM vessels "
                        + "WHERE mmsi IN (" + placeholders + ")",
                rs -> {
                    out.put(rs.getLong("mmsi"), new RegRow(
                            rs.getString("registration_no"),
                            rs.getString("name"),
                            rs.getString("type"),
                            (Float) rs.getObject("length_m"),
                            rs.getString("home_port")));
                },
                mmsis.toArray());
        return out;
    }

    /**
     * Loads the local Westfjords fleet once and builds two lookup maps for vessels
     * the MMSI join missed: accent-folded name → row, and umdæmismerking → row.
     * Each map keeps ONLY keys that are unique within the local fleet — a name or
     * marking shared by two boats is dropped so we never guess a registration number.
     */
    private LocalRegistry loadLocalRegistry() {
        Map<String, RegRow> byName = new HashMap<>();
        Set<String> dupName = new HashSet<>();
        Map<String, RegRow> byMark = new HashMap<>();
        Set<String> dupMark = new HashSet<>();
        jdbc.query(
                "SELECT registration_no, name, type, length_m, home_port, district_no FROM vessels "
                        + "WHERE (" + LOCAL_PORTS_SQL + ") AND name IS NOT NULL",
                rs -> {
                    RegRow rr = new RegRow(
                            rs.getString("registration_no"),
                            rs.getString("name"),
                            rs.getString("type"),
                            (Float) rs.getObject("length_m"),
                            rs.getString("home_port"));
                    String f = foldName(rs.getString("name"));
                    if (f != null) {
                        if (byName.putIfAbsent(f, rr) != null) dupName.add(f);
                    }
                    String mark = markFromDistrict(rs.getString("district_no"));
                    if (mark != null) {
                        if (byMark.putIfAbsent(mark, rr) != null) dupMark.add(mark);
                    }
                });
        dupName.forEach(byName::remove);
        dupMark.forEach(byMark::remove);
        return new LocalRegistry(byName, byMark);
    }

    /** Fallback when Datalastic is unavailable: deterministic split of the local registry. */
    private StatusResponse registryFallback() {
        List<RegRow2> regulars = jdbc.query(
                "SELECT id, registration_no, name, type, length_m, home_port, mmsi, imo "
                        + "FROM vessels WHERE (" + LOCAL_PORTS_SQL + ") AND name IS NOT NULL "
                        + "ORDER BY id LIMIT " + (MAX_PER_SIDE * 4),
                (rs, rn) -> new RegRow2(
                        rs.getInt("id"),
                        rs.getString("registration_no"),
                        rs.getString("name"),
                        rs.getString("type"),
                        (Float) rs.getObject("length_m"),
                        rs.getString("home_port"),
                        (Long) rs.getObject("mmsi"),
                        rs.getString("imo")));
        List<VesselRow> inPort = new ArrayList<>();
        List<VesselRow> atSea = new ArrayList<>();
        for (RegRow2 r : regulars) {
            String label = (r.regno() != null && !r.regno().isBlank())
                    ? r.name() + " (IS-" + r.regno() + ")"
                    : r.name();
            VesselRow row = new VesselRow(r.name(), label, r.regno(), r.type(), r.lengthM(), r.homePort(),
                    null, r.mmsi(), r.imo(), null, true);
            if (r.id() % 2 == 0) {
                if (inPort.size() < MAX_PER_SIDE) inPort.add(row);
            } else {
                if (atSea.size() < MAX_PER_SIDE) atSea.add(row);
            }
        }
        return new StatusResponse(inPort, atSea, "registry-fallback", Instant.now().toString());
    }

    // ── name / district-marking matching ─────────────────────────────────────

    // Trailing umdæmismerking in an AIS name, e.g. "BLIKI IS 414" → IS + 414.
    private static final java.util.regex.Pattern AIS_MARK =
            java.util.regex.Pattern.compile("([A-Z]{2})\\s+0*([0-9]+)\\s*$");
    // Leading umdæmismerking in a registry district_no, e.g. "ÍS-414 (…)" → IS + 414.
    private static final java.util.regex.Pattern REG_MARK =
            java.util.regex.Pattern.compile("^([A-Z]{2})-0*([0-9]+)");

    /**
     * Accent-folds and upper-cases a vessel name so the ASCII names the AIS feed
     * transmits ("KRISTIN", "SKALAVIK") match the accented registry spellings
     * ("KRISTÍN", "SKÁLAVÍK"). NFD strips the combining accents; the Icelandic
     * letters NFD leaves intact (Þ, Ð, Æ) are mapped explicitly.
     */
    private static String foldName(String s) {
        if (s == null) return null;
        String n = java.text.Normalizer.normalize(s, java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "");
        n = n.replace("Þ", "TH").replace("þ", "th")
                .replace("Ð", "D").replace("ð", "d")
                .replace("Æ", "AE").replace("æ", "ae")
                .toUpperCase(java.util.Locale.ROOT).trim();
        return n.isEmpty() ? null : n;
    }

    /** Canonical "IS-414" key from an AIS name's trailing marking, or null. */
    private static String markFromAisName(String aisName) {
        if (aisName == null) return null;
        var m = AIS_MARK.matcher(aisName.toUpperCase(java.util.Locale.ROOT).trim());
        return m.find() ? m.group(1) + "-" + Integer.parseInt(m.group(2)) : null;
    }

    /** Canonical "IS-414" key from a registry district_no, or null. */
    private static String markFromDistrict(String districtNo) {
        String folded = foldName(districtNo);
        if (folded == null) return null;
        var m = REG_MARK.matcher(folded);
        return m.find() ? m.group(1) + "-" + Integer.parseInt(m.group(2)) : null;
    }

    // ── small helpers ───────────────────────────────────────────────────────

    private static String strOrNull(Object o) {
        return o == null ? null : o.toString();
    }

    private static Long asLong(Object o) {
        if (o == null) return null;
        try {
            return Long.valueOf(o.toString().trim());
        } catch (Exception e) {
            return null;
        }
    }

    private static double asDouble(Object o) {
        if (o == null) return 0.0;
        try {
            return Double.parseDouble(o.toString().trim());
        } catch (Exception e) {
            return 0.0;
        }
    }

    private static Float asFloat(Object o) {
        if (o == null) return null;
        try {
            return Float.valueOf(o.toString().trim());
        } catch (Exception e) {
            return null;
        }
    }

    // ── DTOs ────────────────────────────────────────────────────────────────

    /** A row in the Fleet "in port" / "at sea" lists. */
    public record VesselRow(
            String name,
            String displayLabel,
            String registrationNo,
            String type,
            Float lengthM,
            String homePort,
            Double speedKn,
            Long mmsi,
            String imo,
            String destination,
            boolean inRegistry) {}

    public record StatusResponse(
            List<VesselRow> inPort,
            List<VesselRow> atSea,
            String source,
            String snapshotAt) {}

    // internal-only carriers
    private record RegRow(String regno, String name, String type, Float lengthM, String homePort) {}

    private record RegRow2(int id, String regno, String name, String type, Float lengthM,
                           String homePort, Long mmsi, String imo) {}

    /** Local-fleet fallback lookups, each holding only unambiguous keys. */
    private record LocalRegistry(Map<String, RegRow> byName, Map<String, RegRow> byMark) {}
}
