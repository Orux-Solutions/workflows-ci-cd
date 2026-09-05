#!/usr/bin/env python3
"""Safely pull and redeploy a configured Docker Compose stack."""
import argparse, fcntl, json, os, stat, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

TRUTHY = {"1", "true", "yes", "on"}
SERVICE_METADATA = {
    "admin-backend": "ADMIN_BACKEND",
    "admin-frontend": "ADMIN_FRONTEND",
    "business-backend": "BUSINESS_BACKEND",
    "business-frontend": "BUSINESS_FRONTEND",
    "client-backend": "CLIENT_BACKEND",
    "client-frontend": "CLIENT_FRONTEND",
}


def enabled(value):
    return str(value or "").strip().lower() in TRUTHY

def runner_replicas(env):
    value = str(env.get("GITHUB_RUNNER_REPLICAS", "5")).strip()
    try:
        replicas = int(value)
    except ValueError:
        raise ValueError("GITHUB_RUNNER_REPLICAS must be a positive integer") from None
    if replicas < 1:
        raise ValueError("GITHUB_RUNNER_REPLICAS must be a positive integer")
    return replicas

def load_env(path):
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1); values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    token_file = values.get("CLOUDFLARE_TUNNEL_TOKEN_FILE")
    if token_file and not values.get("CLOUDFLARE_TUNNEL_TOKEN"):
        token_path = Path(token_file).expanduser()
        if token_path.exists():
            token = token_path.read_text().strip()
            if token.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
                token = token.split("=", 1)[1].strip().strip('"').strip("'")
            values["CLOUDFLARE_TUNNEL_TOKEN"] = token
    return values

def compose_command(args, env):
    command = ["docker", "compose", "--env-file", str(args.env_file), "-f", str(args.compose)]
    if env.get("_ORUX_RUNNER_PROFILE_ACTIVE") == "true":
        command.extend(["--profile", "github"])
    return command


def compose(args, env, *parts):
    return subprocess.run([*compose_command(args, env), *parts], check=True, text=True, env=env)


def hydrate_deployment_metadata(args, env, services):
    """Read immutable release metadata from the local images pulled as latest."""
    result = subprocess.run(
        [*compose_command(args, env), "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    model = json.loads(result.stdout)
    for service, prefix in SERVICE_METADATA.items():
        if service not in services or service not in model.get("services", {}):
            continue
        image = model["services"][service].get("image")
        if not image:
            continue
        try:
            inspected = subprocess.run(
                ["docker", "image", "inspect", image],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            details = json.loads(inspected.stdout)[0]
        except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError) as exc:
            print(f"Notice: cannot inspect release metadata for {service}: {exc}", file=sys.stderr)
            continue
        labels = details.get("Config", {}).get("Labels") or {}
        release = labels.get("io.orux.release") or labels.get("org.opencontainers.image.version")
        revision = labels.get("org.opencontainers.image.revision")
        if not release or release == "latest":
            identifier = (details.get("RepoDigests") or [details.get("Id", "unknown")])[0]
            fingerprint = identifier.rsplit("sha256:", 1)[-1][:12]
            release = f"latest@{fingerprint}"
        env[f"{prefix}_VERSION"] = release
        env[f"{prefix}_COMMIT"] = revision or env.get(f"{prefix}_COMMIT", "unknown")
        print(f"Deployment metadata: {service}={release} ({env[f'{prefix}_COMMIT'][:12]})")


def configure_runner(env):
    if not enabled(env.get("ORUX_RUNNER_ENABLED")):
        return False
    required = [
        "GITHUB_RUNNER_APP_ID",
        "GITHUB_RUNNER_APP_INSTALLATION_ID",
        "GITHUB_RUNNER_GROUP_ID",
        "GITHUB_RUNNER_APP_PRIVATE_KEY_FILE",
    ]
    missing = [key for key in required if not env.get(key)]
    key_file = Path(env.get("GITHUB_RUNNER_APP_PRIVATE_KEY_FILE", ""))
    if not missing and not key_file.is_file():
        missing.append("GITHUB_RUNNER_APP_PRIVATE_KEY_FILE (file not found)")
    if missing:
        print(
            "Notice: Orux runner disabled because its secure configuration is incomplete: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return False
    env["_ORUX_RUNNER_PROFILE_ACTIVE"] = "true"
    return True


def authenticate_ghcr(env):
    username = env.get("GHCR_USERNAME", "").strip()
    token_file = env.get("GHCR_TOKEN_FILE", "").strip()
    if not username and not token_file:
        return False
    if not username or not token_file:
        print("Notice: GHCR login skipped because GHCR_USERNAME/GHCR_TOKEN_FILE is incomplete.", file=sys.stderr)
        return False
    path = Path(token_file)
    if not path.is_file():
        print(f"Notice: GHCR token file does not exist: {path}", file=sys.stderr)
        return False
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        print(f"Notice: refusing GHCR token file with insecure mode {mode:04o}: {path}", file=sys.stderr)
        return False
    if path.stat().st_uid != os.geteuid():
        print(f"Notice: GHCR token file must belong to the deployer user: {path}", file=sys.stderr)
        return False
    token = path.read_text().strip()
    if not token:
        print(f"Notice: GHCR token file is empty: {path}", file=sys.stderr)
        return False
    try:
        subprocess.run(
            ["docker", "login", "ghcr.io", "--username", username, "--password-stdin"],
            input=token,
            check=True,
            text=True,
            env=env,
            stdout=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Notice: GHCR authentication failed ({exc}); retaining local images.", file=sys.stderr)
        return False

def healthy(url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200: return True
        except (urllib.error.URLError, OSError, TimeoutError): time.sleep(2)
    return False

def deploy(args):
    env = load_env(args.env_file)
    services = (args.services or env.get("ORUX_DEPLOY_SERVICES", "")).split()
    authenticate_ghcr(env)
    if configure_runner(env):
        for service in ("buildkit", "github-runner"):
            if service not in services:
                services.append(service)
    # A Cloudflare Tunnel is opt-in. The token is created in the Cloudflare
    # dashboard and kept only in the local .env file.
    if env.get("CLOUDFLARE_TUNNEL_TOKEN") and "cloudflared" not in services:
        services.append("cloudflared")
    try:
        compose(args, env, "pull", *services)
    except Exception as exc:
        print(f"Notice: pull partial or failed ({exc}), proceeding...", file=sys.stderr)
    if enabled(env.get("ORUX_BUILD_LOCAL")):
        compose(args, env, "build", *services)
    hydrate_deployment_metadata(args, env, services)
    # Do not remove orphaned containers: runner replicas may be managed by a
    # separate scaling command and must not be taken offline by a poll cycle.
    up_args = ["up", "-d"]
    if "github-runner" in services:
        up_args.extend(["--scale", f"github-runner={runner_replicas(env)}"])
    compose(args, env, *up_args, *services)
    health_url = args.health_url or env.get("ORUX_HEALTH_URL", "")
    if health_url and not healthy(health_url, args.health_timeout):
        print(f"Healthcheck failed: {health_url}", file=sys.stderr); return 1
    print(f"Orux stack deployed: {', '.join(services)}"); return 0

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--compose", type=Path, default=Path("compose.yaml")); parser.add_argument("--env-file", type=Path, default=Path(".env")); parser.add_argument("--services", default=""); parser.add_argument("--health-url", default=""); parser.add_argument("--health-timeout", type=int, default=90); parser.add_argument("--once", action="store_true"); parser.add_argument("--interval", type=int, default=0)
    args = parser.parse_args(); args.compose = args.compose.resolve(); args.env_file = args.env_file.resolve()
    if not args.services and not load_env(args.env_file).get("ORUX_DEPLOY_SERVICES", ""):
        parser.error("configure --services or ORUX_DEPLOY_SERVICES")
    with (args.env_file.parent / ".orux-deploy.lock").open("w") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: print("Another Orux deployment is already running.", file=sys.stderr); return 2
        while True:
            result = deploy(args)
            if args.once or not args.interval or result: return result
            time.sleep(args.interval)
if __name__ == "__main__": sys.exit(main())
