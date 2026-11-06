#!/usr/bin/env python3
"""Run JMeter phases and measure Actuator COUNT in three 10-second windows."""
import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8082"
RESULTS = ROOT / "results"


def get(path):
    with urlopen(BASE + path, timeout=30) as response:
        return json.load(response)


def sample(mode):
    url = "/actuator/metrics/http.server.requests?" + urlencode({"tag": "uri:/work/" + mode})
    before = time.monotonic()
    wall = time.time()
    metric = get(url)
    after = time.monotonic()
    count = next(item["value"] for item in metric["measurements"] if item["statistic"] == "COUNT")
    return {"count": count, "monotonic": (before + after) / 2, "epoch": wall + (after - before) / 2,
            "roundtrip_ms": (after - before) * 1000, "metric": metric}


def single_request():
    get("/work/platform?delayMs=1")
    before = sample("platform")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(get, "/work/platform?delayMs=3000")
        time.sleep(1)
        during = sample("platform")
        result = future.result(timeout=10)
    time.sleep(max(0, before["monotonic"] + 10 - time.monotonic()))
    after = sample("platform")
    seconds = after["monotonic"] - before["monotonic"]
    assert during["count"] == before["count"], "COUNT must not include unfinished request"
    assert after["count"] - before["count"] == 1
    evidence = {"before": before, "during": during, "after": after, "request": result,
                "elapsed_seconds": seconds, "throughput": 1 / seconds}
    (RESULTS / "single-long-request.json").write_text(json.dumps(evidence, indent=2))
    print("Single 3s request: COUNT unchanged while running; +1 over %.3fs" % seconds, flush=True)


def summarize_jtl(path):
    with path.open() as file:
        rows = list(csv.DictReader(file))
    assert rows, "JMeter did not produce samples"
    elapsed = sorted(float(row["elapsed"]) for row in rows)
    errors = sum(row["success"].lower() != "true" for row in rows)
    start = min(int(row["timeStamp"]) for row in rows)
    end = max(int(row["timeStamp"]) + int(row["elapsed"]) for row in rows)
    return {"requests": len(rows), "errors": errors, "error_percent": 100 * errors / len(rows),
            "mean_ms": statistics.mean(elapsed), "p95_ms": elapsed[math.ceil(.95 * len(elapsed)) - 1],
            "whole_run_rps": len(rows) / ((end - start) / 1000), "start_epoch": start / 1000,
            "end_epoch": end / 1000, "response_codes": sorted(set(row["responseCode"] for row in rows))}


def phase(jmeter, name, mode, duration, errors=False):
    get("/work/" + mode + "?delayMs=1")  # Register the URI timer before reading COUNT.
    jtl = RESULTS / (name + ".jtl")
    if jtl.exists():
        raise RuntimeError(str(jtl) + " already exists; use a clean results directory for a new experiment")
    environment = os.environ.copy()
    if environment.get("JMETER_JAVA_HOME"):
        environment["JAVA_HOME"] = environment["JMETER_JAVA_HOME"]
    java_home = environment.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else "java"
    # Прямой запуск JAR корректно обрабатывает пробелы в путях на macOS/Windows.
    command = [java, "-Xms256m", "-Xmx512m", "-Djava.awt.headless=true", "-jar", str(jmeter), "-n", "-t", str(ROOT / "load/compare.jmx"), "-l", str(jtl),
               "-j", str(RESULTS / (name + "-jmeter.log")), "-Jmode=" + mode,
               "-Jusers=200", "-Jramp=5", "-Jduration=" + str(duration), "-JdelayMs=500",
               "-JerrorEvery=" + ("10" if errors else "0")]
    print("Starting " + name, flush=True)
    started = time.time()
    with (RESULTS / (name + "-console.txt")).open("w") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            snapshots = []
            if not errors:
                time.sleep(15)
                snapshots.append(sample(mode))
                for _ in range(3):
                    time.sleep(max(0, snapshots[-1]["monotonic"] + 10 - time.monotonic()))
                    assert process.poll() is None, "JMeter exited during the measurement window"
                    snapshots.append(sample(mode))
            process.wait(timeout=duration + 40)
            assert process.returncode == 0, "JMeter failed; see console log"
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
    windows = []
    for first, last in zip(snapshots, snapshots[1:]):
        seconds = last["monotonic"] - first["monotonic"]
        windows.append({"count_before": first["count"], "count_after": last["count"],
                        "elapsed_seconds": seconds, "throughput": (last["count"] - first["count"]) / seconds,
                        "from_epoch": first["epoch"], "to_epoch": last["epoch"]})
    summary = {"phase": name, "mode": mode, "users": 200, "delay_ms": 500,
               "controlled_errors": errors, "started_epoch": started, "ended_epoch": time.time(),
               "samples": snapshots, "windows": windows, "jmeter": summarize_jtl(jtl)}
    if not errors:
        assert summary["jmeter"]["errors"] == 0, "Unexpected errors in main comparison"
    else:
        assert summary["jmeter"]["response_codes"] == ["200", "503"]
    (RESULTS / (name + ".json")).write_text(json.dumps(summary, indent=2))
    print(name + ": " + json.dumps({"windows": windows, "jmeter": summary["jmeter"]}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jmeter", type=Path, default=ROOT / ".tools/apache-jmeter-5.6.3/bin/ApacheJMeter.jar")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    single_request()
    phases = []
    phases.append(phase(args.jmeter, "platform", "platform", 60))
    time.sleep(6)
    phases.append(phase(args.jmeter, "virtual", "virtual", 60))
    time.sleep(6)
    phases.append(phase(args.jmeter, "controlled-errors", "virtual", 35, errors=True))
    (RESULTS / "summary.json").write_text(json.dumps(phases, indent=2))
    print("Measurements saved to " + str(RESULTS), flush=True)


if __name__ == "__main__":
    main()
