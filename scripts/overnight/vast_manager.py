"""Own one labeled Vast.ai instance for Database Surgeon. Never touch other labels.

Lifecycle: search → create (label=database-surgeon-sft) → wait SSH → train →
serve via loopback tunnel → destroy. Hard budget: max $/hr and total overnight $.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from . import state

ROOT = Path(__file__).resolve().parents[2]
LABEL = "database-surgeon-sft"
BASE = os.getenv("VAST_BASE_MODEL", "unsloth/Qwen2.5-Coder-7B-Instruct")
# Runtime image pulls much faster than *-devel; enough for Unsloth/TRL.
IMAGE = os.getenv("VAST_IMAGE", "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime")
REMOTE_DIR = "/workspace/surgeon"
# Account key registered with Vast (same as token-routing); not a default id_*.
SSH_KEY = Path(os.getenv("VAST_SSH_KEY", str(Path.home() / ".ssh/token-routing-gpu")))


def _ssh_opts() -> list[str]:
    opts = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=20",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes"]
    if SSH_KEY.exists():
        opts += ["-i", str(SSH_KEY)]
    return opts


def _env():
    env = dict(os.environ)
    # Prefer .env.local via caller; CLI also reads ~/.config/vastai/vast_api_key.
    return env


def _vastai_bin() -> str:
    for candidate in (
        os.getenv("VASTAI_BIN"),
        str(Path.home() / ".local/bin/vastai"),
        "/opt/homebrew/bin/vastai",
        "vastai",
    ):
        if not candidate:
            continue
        if candidate == "vastai" or Path(candidate).exists():
            return candidate
    return "vastai"


def _run(args: list[str], check=True, raw=False) -> subprocess.CompletedProcess:
    cmd = [_vastai_bin(), *args]
    if raw and "--raw" not in args:
        cmd.append("--raw")
    return subprocess.run(cmd, capture_output=True, text=True, env=_env(), check=check)


def _json(args: list[str]):
    result = _run(args, raw=True)
    text = result.stdout.strip() or "null"
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"vastai {args[0]} returned non-JSON: {result.stdout[:300]} {result.stderr[:300]}") from exc


def configure_key():
    key = os.getenv("VAST_API_KEY")
    if not key:
        cfg = Path.home() / ".config/vastai/vast_api_key"
        if cfg.exists():
            key = cfg.read_text().strip()
    if not key:
        raise RuntimeError("VAST_API_KEY missing")
    _run(["set", "api-key", key], check=False)
    return True


def credit_usd() -> float | None:
    try:
        user = _json(["show", "user"])
        if isinstance(user, list) and user:
            return float(user[0].get("credit") or 0)
        if isinstance(user, dict):
            return float(user.get("credit") or 0)
    except Exception:  # noqa: BLE001
        return None
    return None


def our_instances():
    instances = _json(["show", "instances"]) or []
    if not isinstance(instances, list):
        return []
    return [i for i in instances if (i.get("label") or "") == LABEL]


def foreign_running():
    instances = _json(["show", "instances"]) or []
    return [i for i in (instances or [])
            if i.get("actual_status") == "running" and (i.get("label") or "") != LABEL]


def find_offer(max_dph: float):
    # compute_cap>=800 → Ampere+ (skip V100/sm_70; modern torch/unsloth lack those kernels).
    query = (f"gpu_ram>=24 num_gpus=1 verified=true reliability>0.97 "
             f"compute_cap>=800 dph_total<={max_dph} inet_down>100")
    offers = _json(["search", "offers", query, "-o", "dph_total"]) or []
    if not offers:
        return None
    return offers[0]


def create_instance(max_dph: float) -> int:
    existing = our_instances()
    for inst in existing:
        status = inst.get("actual_status")
        age = time.time() - float(inst.get("start_date") or time.time())
        compute_cap = int(inst.get("compute_cap") or 0)
        # Modern torch/unsloth need Ampere+ (sm>=8.0 / compute_cap>=800).
        if compute_cap and compute_cap < 800:
            state.log(f"vast: instance {inst['id']} {inst.get('gpu_name')} compute_cap={compute_cap} too old — destroying")
            destroy(int(inst["id"]))
            continue
        # Drop boxes stuck pulling/extracting forever; recreate on a fresh host.
        if status == "loading" and age > 25 * 60:
            state.log(f"vast: instance {inst['id']} loading for {age/60:.0f}m — destroying")
            destroy(int(inst["id"]))
            continue
        if status in ("running", "loading", "created"):
            state.log(f"vast: reusing instance {inst['id']} ({inst.get('gpu_name')}) status={status}")
            return int(inst["id"])
    offer = find_offer(max_dph)
    if not offer:
        raise RuntimeError(f"No Vast offer under ${max_dph}/hr")
    offer_id = offer["id"]
    dph = offer.get("dph_total")
    gpu = offer.get("gpu_name")
    state.log(f"vast: creating offer {offer_id} {gpu} ${dph}/hr label={LABEL}")
    # --label keeps this instance distinguishable from token-routing boxes.
    result = _run([
        "create", "instance", str(offer_id),
        "--image", IMAGE,
        "--disk", "80",
        "--ssh",
        "--direct",
        "--label", LABEL,
        "--onstart-cmd", "bash -lc 'mkdir -p /workspace/surgeon'",
    ])
    # create prints the new id; also re-list
    time.sleep(3)
    ours = our_instances()
    if not ours:
        # fallback parse
        for token in (result.stdout + result.stderr).split():
            if token.isdigit() and len(token) >= 6:
                return int(token)
        raise RuntimeError(f"vast create failed: {result.stdout} {result.stderr}")
    inst_id = int(ours[0]["id"])
    data = state.read()
    data["vast_instance_id"] = inst_id
    state.write(data)
    state.spend("vast_create", None, f"id={inst_id} gpu={gpu} dph={dph}")
    return inst_id


def wait_ready(instance_id: int, timeout_s=900):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        instances = {int(i["id"]): i for i in (_json(["show", "instances"]) or [])}
        inst = instances.get(instance_id)
        if not inst:
            raise RuntimeError(f"instance {instance_id} disappeared")
        status = (inst.get("actual_status") or inst.get("status_msg") or "").lower()
        state.log(f"vast: instance {instance_id} status={status!r} ssh={bool(inst.get('ssh_host'))}")
        if status in ("running", "running ") or (inst.get("ssh_host") and "running" in status):
            time.sleep(15)
            return inst
        if inst.get("ssh_host") and status in ("", "none") and inst.get("actual_status") is None:
            # Some API payloads omit actual_status briefly while ssh is already up.
            time.sleep(10)
            if inst.get("ssh_host"):
                return inst
        if any(tok in status for tok in ("exit", "error", "offline", "dead")):
            raise RuntimeError(f"instance failed: {status} {inst.get('status_msg')}")
        time.sleep(20)
    raise TimeoutError(f"instance {instance_id} not ready in {timeout_s}s")


def ssh_target(instance_id: int) -> tuple[str, str, str]:
    """Return (port, user_host, full ssh -p ... user@host string parts)."""
    result = _run(["ssh-url", str(instance_id)])
    url = (result.stdout or result.stderr).strip().splitlines()[-1]
    # ssh://root@host:port
    if not url.startswith("ssh://"):
        raise RuntimeError(f"bad ssh-url: {url}")
    body = url[len("ssh://"):]
    user_host, port = body.rsplit(":", 1)
    return port, user_host, f"-p {port} {user_host}"


def ssh(instance_id: int, remote: str, check=True, timeout=None):
    port, user_host, _ = ssh_target(instance_id)
    cmd = ["ssh", *_ssh_opts(), "-p", port, user_host, remote]
    return subprocess.run(cmd, capture_output=True, text=True, check=check, timeout=timeout)


def scp_to(instance_id: int, local: Path, remote_name: str):
    port, user_host, _ = ssh_target(instance_id)
    remote = f"{user_host}:{REMOTE_DIR}/{remote_name}"
    ssh(instance_id, f"mkdir -p {REMOTE_DIR}", check=False)
    scp = ["scp", *_ssh_opts(), "-P", port, str(local), remote]
    # scp uses -o via ssh; IdentitiesOnly/BatchMode already in _ssh_opts.
    subprocess.run(scp, check=True, capture_output=True, text=True)


def destroy(instance_id: int | None = None):
    data = state.read()
    instance_id = instance_id or data.get("vast_instance_id")
    if not instance_id:
        for inst in our_instances():
            instance_id = int(inst["id"])
            break
    if not instance_id:
        state.log("vast: nothing to destroy")
        return
    # Safety: only destroy our label.
    instances = {int(i["id"]): i for i in (_json(["show", "instances"]) or [])}
    inst = instances.get(int(instance_id))
    if inst and (inst.get("label") or "") != LABEL:
        raise RuntimeError(f"refusing to destroy foreign instance {instance_id} label={inst.get('label')}")
    state.log(f"vast: destroying {instance_id}")
    _run(["destroy", "instance", str(instance_id), "-y"], check=False)
    data["vast_instance_id"] = None
    state.write(data)
    state.spend("vast_destroy", None, f"id={instance_id}")


def upload_and_train(instance_id: int):
    sft = ROOT / ".local/training/fireworks_sft.jsonl"
    dpo = ROOT / ".local/training/dpo.jsonl"
    train_py = ROOT / "scripts/finetune/vast/train_trl.py"
    if not sft.exists() or sft.stat().st_size < 100:
        raise RuntimeError("SFT data missing; train-data phase incomplete")
    scp_to(instance_id, sft, "sft.jsonl")
    if dpo.exists():
        scp_to(instance_id, dpo, "dpo.jsonl")
    scp_to(instance_id, train_py, "train_trl.py")
    # Unsloth needs a CUDA torch image; install into the pytorch container.
    # Fast path: 1 epoch SFT; DPO skipped when file empty (train_trl already guards).
    epochs = os.getenv("VAST_SFT_EPOCHS", "1")
    setup = (
        f"cd {REMOTE_DIR} && "
        "pip install -q --upgrade pip && "
        "pip install -q --default-timeout=180 --retries 10 "
        "'unsloth' trl datasets accelerate peft bitsandbytes && "
        f"python train_trl.py --base {shlex.quote(BASE)} --sft sft.jsonl "
        f"--dpo dpo.jsonl --epochs {shlex.quote(epochs)} --rank 16 "
        f"> train.log 2>&1"
    )
    state.log(f"vast: starting SFT epochs={epochs} (DPO only if pairs exist)")
    # Run detached so our SSH can return after launch; we poll the log.
    ssh(instance_id, f"bash -lc {shlex.quote('nohup bash -lc ' + shlex.quote(setup) + ' >/workspace/surgeon/nohup.out 2>&1 & echo $!')}")
    return poll_train(instance_id)


def poll_train(instance_id: int, timeout_s=4 * 3600):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        # Match the python train argv, not the wrapping bash that quotes train_trl.py.
        probe = ssh(instance_id,
                    f"bash -lc '"
                    f"if ps -eo args | grep -E \"^([^ ]*/)?python[0-9.]* .*train_trl\\.py\" | grep -v grep >/dev/null; "
                    f"then echo RUNNING; "
                    f"elif ps -eo args | grep -E \"^([^ ]*/)?pip[0-9.]* install\" | grep -v grep >/dev/null; "
                    f"then echo SETUP; "
                    f"elif [ -d {REMOTE_DIR}/out/sft ]; then echo DONE; "
                    f"else echo WAIT; fi; "
                    f"tail -n 5 {REMOTE_DIR}/train.log 2>/dev/null; "
                    f"tail -n 2 {REMOTE_DIR}/nohup.out 2>/dev/null'",
                    check=False)
        out = (probe.stdout or "").strip()
        state.log(f"vast train: {out.splitlines()[0] if out else '…'}")
        if out.startswith("DONE") or "\nDONE" in out:
            pull_adapters(instance_id)
            return True
        if "Traceback" in out or ("ERROR" in out and "RUNNING" not in out and "SETUP" not in out):
            if out.startswith("WAIT"):
                raise RuntimeError(f"training failed:\n{out}")
        time.sleep(60)
    raise TimeoutError("training timed out")


def pull_adapters(instance_id: int):
    dest = ROOT / ".local/training/adapters/vast-qwen25-coder-7b"
    dest.mkdir(parents=True, exist_ok=True)
    port, user_host, _ = ssh_target(instance_id)
    for name in ("out/sft", "out/dpo"):
        subprocess.run([
            "scp", *_ssh_opts(), "-P", port, "-r",
            f"{user_host}:{REMOTE_DIR}/{name}", str(dest),
        ], check=False, capture_output=True, text=True)
    state.log(f"vast: adapters pulled to {dest}")


def start_vllm(instance_id: int, local_port=8000):
    """Serve LoRA on the instance and open a loopback SSH tunnel."""
    adapter = "out/dpo" if True else "out/sft"
    remote = (
        f"cd {REMOTE_DIR} && pip install -q vllm && "
        f"pkill -f 'vllm serve' || true; "
        f"nohup python -m vllm.entrypoints.openai.api_server "
        f"--model {shlex.quote(BASE)} --enable-lora "
        f"--lora-modules specialist={adapter} "
        f"--host 127.0.0.1 --port 8000 --max-model-len 8192 "
        f"> vllm.log 2>&1 &"
    )
    # Prefer SFT adapter if DPO missing.
    check = ssh(instance_id, f"bash -lc 'if [ -d {REMOTE_DIR}/out/dpo ]; then echo dpo; "
                             f"elif [ -d {REMOTE_DIR}/out/sft ]; then echo sft; else echo none; fi'")
    which = (check.stdout or "").strip()
    if which == "none":
        raise RuntimeError("no adapter on instance")
    adapter = f"out/{which}"
    remote = remote.replace("out/dpo", adapter)
    ssh(instance_id, f"bash -lc {shlex.quote(remote)}", check=False)
    time.sleep(30)
    port, user_host, _ = ssh_target(instance_id)
    # Background tunnel
    tunnel = subprocess.Popen(
        ["ssh", *_ssh_opts(), "-N",
         "-L", f"127.0.0.1:{local_port}:127.0.0.1:8000", "-p", port, user_host],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    data = state.read()
    data["vast_tunnel_pid"] = tunnel.pid
    state.write(data)
    state.log(f"vast: vLLM tunnel pid={tunnel.pid} -> 127.0.0.1:{local_port}")
    # wait until health
    for _ in range(60):
        probe = subprocess.run(
            ["curl", "-s", "-m", "2", f"http://127.0.0.1:{local_port}/v1/models"],
            capture_output=True, text=True)
        if probe.returncode == 0 and "specialist" in probe.stdout or "data" in probe.stdout:
            return local_port
        time.sleep(10)
    return local_port
