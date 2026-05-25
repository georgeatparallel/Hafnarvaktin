package is.fljotavik.backend.camera;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/cameras")
public class CameraController {

    private final CameraRepository cameraRepository;

    public CameraController(CameraRepository cameraRepository) {
        this.cameraRepository = cameraRepository;
    }

    @GetMapping
    public List<CameraResponse> list() {
        return cameraRepository.findAll().stream()
                .map(CameraResponse::from)
                .toList();
    }

    public record CameraResponse(Integer id, String name, String location) {
        static CameraResponse from(Camera camera) {
            return new CameraResponse(camera.getId(), camera.getName(), camera.getLocation());
        }
    }
}
