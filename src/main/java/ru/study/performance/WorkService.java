package ru.study.performance;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

@Service
public class WorkService {
    private final ExecutorService platformWorkers;
    private final ExecutorService virtualWorkers;

    public WorkService(@Qualifier("platformWorkers") ExecutorService platformWorkers,
                       @Qualifier("virtualWorkers") ExecutorService virtualWorkers) {
        this.platformWorkers = platformWorkers;
        this.virtualWorkers = virtualWorkers;
    }

    public CompletableFuture<Result> execute(boolean virtual, long delayMs, boolean fail) {
        return CompletableFuture.supplyAsync(() -> {
            long start = System.nanoTime();
            try {
                // Управляемая имитация блокирующего ожидания внешнего сервиса, не CPU-работа.
                Thread.sleep(delayMs);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("Work interrupted", ex);
            }
            var thread = Thread.currentThread();
            return new Result(virtual ? "virtual" : "platform", thread.isVirtual(), thread.getName(),
                    (System.nanoTime() - start) / 1_000_000.0, fail);
        }, virtual ? virtualWorkers : platformWorkers);
    }

    public record Result(String mode, boolean virtualThread, String thread, double workMillis,
                         boolean simulatedFailure) { }
}
