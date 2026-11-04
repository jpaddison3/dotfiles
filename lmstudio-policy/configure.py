#!/usr/bin/env python3
"""Configure LM Studio's native idle timers without unloading active models."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time


def write_json(path, value, backups):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backups / (path.name + "." + str(time.time_ns())))
    temporary = path.with_name(path.name + ".idle-policy-new")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def apply(root, models, loaded, ttl, backups):
    settings_path = root / "settings.json"
    settings = json.loads(settings_path.read_text())
    settings.setdefault("developer", {})["jitModelTTL"] = {
        "enabled": True, "ttlSeconds": ttl
    }
    write_json(settings_path, settings, backups)

    data_path = root / ".internal/model-data.json"
    data = json.loads(data_path.read_text())
    # LM Studio stores a SuperJSON Map. Keep its metadata and existing entries.
    entries = dict(data["json"])
    for model in models:
        entries.setdefault(model["indexedModelIdentifier"], {})["uiTTL"] = {
            "enabled": True, "ttlSeconds": ttl
        }
    data["json"] = list(entries.items())
    write_json(data_path, data, backups)

    # Reopening after TTL must retain the current context and parallelism,
    # rather than falling back to LM Studio's otherwise-global 8192 context.
    for model in loaded:
        if model["type"] != "llm":
            continue
        path = (root / ".internal/user-concrete-model-default-config" /
                (model["indexedModelIdentifier"].split("@")[0] + ".json"))
        config = json.loads(path.read_text()) if path.exists() else {
            "preset": "", "operation": {"fields": []}, "load": {"fields": []}
        }
        fields = {field["key"]: field for field in config["load"]["fields"]}
        fields["llm.load.contextLength"] = {
            "key": "llm.load.contextLength", "value": model["contextLength"]
        }
        if model.get("parallel") is not None:
            fields["llm.load.numParallelSessions"] = {
                "key": "llm.load.numParallelSessions", "value": model["parallel"]
            }
        config["load"]["fields"] = list(fields.values())
        write_json(path, config, backups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttl", type=int, default=1800)
    args = parser.parse_args()
    if args.ttl <= 0:
        parser.error("TTL must be positive")
    root = Path.home() / ".lmstudio"
    native = str(root / "bin/lms")
    models = json.loads(subprocess.check_output([native, "ls", "--json"]))
    loaded = json.loads(subprocess.check_output([native, "ps", "--json"]))
    backups = Path.home() / ".cache/agent-tmp/lmstudio-idle-policy/backups"
    apply(root, models, loaded, args.ttl, backups)
    print(json.dumps({"ttl_seconds": args.ttl,
                      "gui_models": len(models),
                      "preserved_load_configs": [m["modelKey"] for m in loaded
                                                 if m["type"] == "llm"]}))


if __name__ == "__main__":
    main()
