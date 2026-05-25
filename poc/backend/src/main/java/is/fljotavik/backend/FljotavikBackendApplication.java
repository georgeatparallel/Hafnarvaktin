package is.fljotavik.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class FljotavikBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(FljotavikBackendApplication.class, args);
    }
}
