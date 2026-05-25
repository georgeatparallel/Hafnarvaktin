package is.fljotavik.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI fljotavikOpenApi() {
        return new OpenAPI().info(new Info()
                .title("Hafnarvaktin Backend API")
                .version("v1")
                .description("REST + WebSocket surface for the Hafnarvaktin YOLO dashboard. "
                        + "The React Native app consumes the same contract."));
    }
}
