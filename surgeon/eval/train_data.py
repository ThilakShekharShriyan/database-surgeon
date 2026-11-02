"""Training data from verified traces of an open teacher (rejection sampling).

Prompts are fresh seeds of non-held-out templates only, so no dev or held-out
instance and no held-out template is ever trained on. The teacher is
gpt-oss-120b inside the harness (rules, best-of-3, repair); a target is kept
only when it passes the development fixtures and is at least 20% faster. When
nothing passes, the target is the original query (abstention). Frontier model
outputs are never used, so the specialist is trained purely on open-model and
rule output.

Outputs (in .local/training/):
  sft.jsonl  chat records: system + user prompt exactly as the specialist sees it
  dpo.jsonl  prompt / chosen / rejected, where rejected changed results on a fixture
  memory.jsonl  verified examples for the retrieval lever
"""

import json
from concurrent.futures import ThreadPoolExecutor

from ..config import ROOT
from .cases import CONTEXT, train_instances
from .llm import Spend
from .registry import OSS_LARGE
from .systems import System, SystemConfig, Verifier, normalize

OUT = ROOT / ".local" / "training"
MEMORY = ROOT / ".local" / "eval_v2" / "memory.jsonl"
TEACHER = SystemConfig(name="teacher-oss120b", provider=OSS_LARGE[0], model=OSS_LARGE[1], rules=True,
                       catalog=True, guide=True, best_of=3, repair=2, precheck=True, verify=True)
# The specialist is prompted exactly like this (catalog + guide, no retrieval).
STUDENT_PROMPT = SystemConfig(name="student-prompt", catalog=True, guide=True)


def answer(sql, rationale):
    return json.dumps({"sql": sql, "rationale": rationale})


def generate(per_template=8, workers=6, ceiling_usd=3.0, log=print):
    verifier = Verifier()
    teacher = System(TEACHER, verifier, spend=Spend(ceiling_usd))
    prompter = System(STUDENT_PROMPT, verifier)
    cases = [dict(c, schema_context=CONTEXT) for c in train_instances(per_template)]
    OUT.mkdir(parents=True, exist_ok=True)
    traces_path = OUT / "teacher_traces.jsonl"
    done = {}
    if traces_path.exists():
        for line in traces_path.read_text().splitlines():
            item = json.loads(line)
            done[item["case"]["id"]] = item

    def one(case):
        if case["id"] in done:
            return done[case["id"]]
        trace = teacher.run(case, 0)
        if any(c.get("transient") for c in trace["calls"]):
            return None
        item = {"case": case, "trace": trace}
        with traces_path.open("a") as handle:
            handle.write(json.dumps(item, default=str) + "\n")
        return item

    with ThreadPoolExecutor(workers) as pool:
        items = [i for i in pool.map(one, cases) if i]
    sft, dpo, memory = [], [], []
    for item in items:
        case, trace = item["case"], item["trace"]
        changed = normalize(trace["result_sql"]) != normalize(case["sql"])
        system, user = prompter._system_prompt(case), prompter._user_prompt(case, _plan(verifier, case), [])
        best = next((c for c in trace["candidates"] if c["verified"] and normalize(c["sql"]) == normalize(trace["result_sql"])), None)
        if changed:
            chosen = answer(trace["result_sql"], f"Verified equivalent on the checks and {best['reduction']:.0%} faster." if best else "Verified rewrite.")
            memory.append({"original": case["sql"], "rewrite": trace["result_sql"], "family": case["family"],
                           "verdict": f"same rows, {best['reduction']:.0%} faster" if best else "same rows, faster"})
        else:
            chosen = answer(case["sql"], "No rewrite was both provably equivalent and at least 20% faster.")
            if case["kind"] == "decoy":
                memory.append({"original": case["sql"], "rewrite": case["sql"], "family": case["family"],
                               "verdict": "already optimal; returned unchanged"})
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        sft.append({"messages": messages + [{"role": "assistant", "content": chosen}],
                    "meta": {"case": case["id"], "template": case["template"], "changed": changed}})
        for wrong in (c for c in trace["candidates"] if c["stage"] == "check"):
            dpo.append({"prompt": messages, "chosen": chosen,
                        "rejected": answer(wrong["sql"], "Rewrite."),
                        "meta": {"case": case["id"], "template": case["template"]}})
    _write(OUT / "sft.jsonl", sft)
    _write(OUT / "dpo.jsonl", dpo)
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    _write(MEMORY, memory)
    stats = {"prompts": len(cases), "traced": len(items), "sft": len(sft),
             "sft_rewrites": sum(r["meta"]["changed"] for r in sft), "dpo_pairs": len(dpo), "memory": len(memory),
             "teacher_cost_usd": teacher.client.spend.usd if teacher.client and teacher.client.spend else None}
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    log(json.dumps(stats))
    return stats


_plans = {}


def _plan(verifier, case):
    if case["sql"] not in _plans:
        try:
            _plans[case["sql"]] = verifier.plan_text(case["sql"])[0]
        except Exception:  # noqa: BLE001
            _plans[case["sql"]] = "unavailable"
    return _plans[case["sql"]]


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def split_for_training(valid_fraction=0.1):
    """Hold out whole templates for MLX/Fireworks validation loss."""
    rows = [json.loads(line) for line in (OUT / "sft.jsonl").read_text().splitlines()]
    templates = sorted({r["meta"]["template"] for r in rows})
    valid_templates = set(templates[::max(2, int(1 / valid_fraction))])
    directory = OUT / "mlx"
    directory.mkdir(parents=True, exist_ok=True)
    train = [{"messages": r["messages"]} for r in rows if r["meta"]["template"] not in valid_templates]
    valid = [{"messages": r["messages"]} for r in rows if r["meta"]["template"] in valid_templates]
    _write(directory / "train.jsonl", train)
    _write(directory / "valid.jsonl", valid)
    _write(OUT / "fireworks_sft.jsonl", [{"messages": r["messages"]} for r in rows])
    return {"train": len(train), "valid": len(valid)}
