#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
phases = json.loads((root / "results/summary.json").read_text())
start = phases[0]["started_epoch"] - 5
end = phases[-1]["ended_epoch"] + 25
dashboard = json.loads((root / "monitoring/grafana/dashboards/red.json").read_text())
export = {"start_epoch": start, "end_epoch": end, "step_seconds": 2, "panels": []}
for panel in dashboard["panels"]:
    for target in panel["targets"]:
        query = {"query": target["expr"], "start": start, "end": end, "step": 2}
        with urlopen("http://localhost:9091/api/v1/query_range?" + urlencode(query), timeout=30) as response:
            series = json.load(response)
        assert series["status"] == "success" and series["data"]["result"], panel["title"]
        export["panels"].append({"title": panel["title"], "legend": target["legendFormat"],
                                 "query": target["expr"], "response": series})
(root / "results/prometheus-series.json").write_text(json.dumps(export, indent=2))
print("Exported", len(export["panels"]), "Grafana query results with original Prometheus samples")
