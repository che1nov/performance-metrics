package ru.study.performance;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class WorkerConfig {
    @Bean(destroyMethod = "close")
    ExecutorService platformWorkers(@Value("${lab.platform-threads:16}") int threads) {
        return new ThreadPoolExecutor(threads, threads, 0, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(1024), Thread.ofPlatform().name("platform-work-", 0).factory(),
                new ThreadPoolExecutor.AbortPolicy());
    }

    @Bean(destroyMethod = "close")
    ExecutorService virtualWorkers() {
        return Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("virtual-work-", 0).factory());
    }
}
