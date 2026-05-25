package is.fljotavik.backend.camera;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "cameras")
public class Camera {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(length = 200)
    private String location;

    @Column(name = "rtsp_url", nullable = false, columnDefinition = "TEXT")
    private String rtspUrl;

    @Column(name = "created_at", insertable = false, updatable = false)
    private Instant createdAt;

    protected Camera() {
        // for JPA
    }

    public Camera(String name, String location, String rtspUrl) {
        this.name = name;
        this.location = location;
        this.rtspUrl = rtspUrl;
    }

    public Integer getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getLocation() {
        return location;
    }

    public String getRtspUrl() {
        return rtspUrl;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
