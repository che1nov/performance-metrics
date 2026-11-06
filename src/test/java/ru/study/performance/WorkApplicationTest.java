package ru.study.performance;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.web.client.TestRestTemplate;
import static org.assertj.core.api.Assertions.assertThat;

@AutoConfigureObservability
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class WorkApplicationTest {
    @Autowired TestRestTemplate http;

    @Test
    void platformActuallyUsesPlatformThread() {
        var response = http.getForEntity("/work/platform?delayMs=10", JsonNode.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getBody().get("virtualThread").asBoolean()).isFalse();
        assertThat(response.getBody().get("thread").asText()).startsWith("platform-work-");
    }

    @Test
    void virtualActuallyUsesVirtualThread() {
        var response = http.getForEntity("/work/virtual?delayMs=10", JsonNode.class);
        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getBody().get("virtualThread").asBoolean()).isTrue();
        assertThat(response.getBody().get("thread").asText()).startsWith("virtual-work-");
    }

    @Test
    void controlledFailureProduces503AndIsObserved() {
        var response = http.getForEntity("/work/virtual?delayMs=10&fail=true", JsonNode.class);
        assertThat(response.getStatusCode().value()).isEqualTo(503);
        var metrics = http.getForObject("/actuator/metrics/http.server.requests?tag=uri:/work/virtual&tag=status:503", JsonNode.class);
        assertThat(metrics.get("measurements").findValues("value")).isNotEmpty();
        assertThat(metrics.get("measurements").get(0).get("value").asDouble()).isGreaterThanOrEqualTo(1);
        var prometheus = http.getForObject("/actuator/prometheus", String.class);
        assertThat(prometheus).contains("http_server_requests_seconds_count", "http_server_requests_seconds_bucket");
    }

    @Test
    void rejectsUnboundedDelay() {
        assertThat(http.getForEntity("/work/platform?delayMs=5001", String.class).getStatusCode().value()).isEqualTo(400);
    }
}
