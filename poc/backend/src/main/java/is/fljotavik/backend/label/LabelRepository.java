package is.fljotavik.backend.label;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface LabelRepository extends JpaRepository<Label, Integer> {
    Optional<Label> findByName(String name);
}
