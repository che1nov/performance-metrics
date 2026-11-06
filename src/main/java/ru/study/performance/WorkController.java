package ru.study.performance;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.RejectedExecutionException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class WorkController {
    private final WorkService service;

    public WorkController(WorkService service) { this.service = service; }

    @GetMapping("/work/platform")
    public CompletableFuture<ResponseEntity<WorkService.Result>> platform(
            @RequestParam(defaultValue = "500") long delayMs,
            @RequestParam(defaultValue = "false") boolean fail) {
        return response(false, delayMs, fail);
    }

    @GetMapping("/work/virtual")
    public CompletableFuture<ResponseEntity<WorkService.Result>> virtual(
            @RequestParam(defaultValue = "500") long delayMs,
            @RequestParam(defaultValue = "false") boolean fail) {
        return response(true, delayMs, fail);
    }

    private CompletableFuture<ResponseEntity<WorkService.Result>> response(boolean virtual, long delayMs, boolean fail) {
        if (delayMs < 1 || delayMs > 5000) throw new IllegalArgumentException("delayMs: от 1 до 5000");
        // Async MVC освобождает поток Tomcat на время работы выбранного executor.
        return service.execute(virtual, delayMs, fail)
                .thenApply(result -> ResponseEntity.status(result.simulatedFailure() ? 503 : 200).body(result));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    ProblemDetail invalid(IllegalArgumentException ex) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
    }

    @ExceptionHandler(RejectedExecutionException.class)
    ProblemDetail overloaded() {
        return ProblemDetail.forStatusAndDetail(HttpStatus.SERVICE_UNAVAILABLE, "Worker queue is full");
    }
}
