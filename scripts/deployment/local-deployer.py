#!/usr/bin/env python3
"""Safely pull and redeploy a configured Docker Compose stack."""
import argparse, fcntl, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

def load_env(path):
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1); values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ); return values

def compose(args, env, *parts):
    return subprocess.run(["docker", "compose", "--env-file", str(args.env_file), "-f", str(args.compose), *parts], check=True, text=True, env=env)

def healthy(url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200: return True
        except (urllib.error.URLError, OSError, TimeoutError): time.sleep(2)
    return False

def deploy(args):
    env = load_env(args.env_file); services = args.services.split()
    compose(args, env, "pull", *services); compose(args, env, "up", "-d", *services)
    if args.health_url and not healthy(args.health_url, args.health_timeout):
        print(f"Healthcheck failed: {args.health_url}", file=sys.stderr); return 1
    print(f"Orux stack deployed: {', '.join(services)}"); return 0

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--compose", type=Path, default=Path("compose.yaml")); parser.add_argument("--env-file", type=Path, default=Path(".env")); parser.add_argument("--services", default=os.environ.get("ORUX_DEPLOY_SERVICES", "")); parser.add_argument("--health-url", default=os.environ.get("ORUX_HEALTH_URL", "")); parser.add_argument("--health-timeout", type=int, default=90); parser.add_argument("--once", action="store_true"); parser.add_argument("--interval", type=int, default=0)
    args = parser.parse_args(); args.compose = args.compose.resolve(); args.env_file = args.env_file.resolve()
    if not args.services: parser.error("configure --services or ORUX_DEPLOY_SERVICES")
    with (args.env_file.parent / ".orux-deploy.lock").open("w") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: print("Another Orux deployment is already running.", file=sys.stderr); return 2
        while True:
            result = deploy(args)
            if args.once or not args.interval or result: return result
            time.sleep(args.interval)
if __name__ == "__main__": sys.exit(main())
