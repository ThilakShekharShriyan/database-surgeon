"""python -m surgeon.eval {build,systems,run,report,freeze}"""

import argparse
import json

from ..config import load_env


def main(argv=None):
    load_env()
    from . import registry
    parser = argparse.ArgumentParser(prog="surgeon.eval")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Validate and freeze the case set (rewrites benchmarks/eval_v2).")
    sub.add_parser("systems", help="List named systems.")
    run = sub.add_parser("run")
    run.add_argument("systems", nargs="+")
    run.add_argument("--split", choices=("dev", "heldout"), default="dev")
    run.add_argument("--trials", type=int, default=3)
    run.add_argument("--workers", type=int, default=6)
    run.add_argument("--max-usd", type=float, default=5.0)
    run.add_argument("--cases", nargs="*")
    report = sub.add_parser("report")
    report.add_argument("--split", choices=("dev", "heldout"), default="dev")
    report.add_argument("--baseline", default="frontier-raw", help="Named saved system to compare against.")
    report.add_argument("--comparison-trial", type=int, default=0,
                        help="Preselected trial for paired tests (default 0; never select by score).")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("systems", nargs="+")
    data = sub.add_parser("train-data", help="Teacher traces -> SFT, DPO and retrieval memory.")
    data.add_argument("--per-template", type=int, default=8)
    data.add_argument("--max-usd", type=float, default=3.0)
    sub.add_parser("train-split", help="Write MLX train/valid and Fireworks SFT files.")
    sub.add_parser("train-router", help="Fit the learned router on dev traces.")
    cascades = sub.add_parser("cascades", help="Replay cascades and router sweeps from stage runs.")
    cascades.add_argument("--split", choices=("dev", "heldout"), default="dev")
    args = parser.parse_args(argv)
    known = registry.systems()

    if args.command == "build":
        from .cases import build
        manifest = build()
        print(json.dumps({k: manifest[k] for k in ("counts", "families", "kinds", "cases_sha256")}, indent=2))
    elif args.command == "systems":
        for name, config in known.items():
            print(name, json.dumps(config.describe()))
    elif args.command == "run":
        from .runner import run as run_system
        from .router import router_for
        for name in args.systems:
            config = known[name]
            router = router_for(config) if config.router else None
            run_system(config, args.split, args.trials, args.workers, args.max_usd, args.cases, router=router)
    elif args.command == "report":
        from .report import write_report
        print(write_report(args.split, args.baseline, args.comparison_trial))
    elif args.command == "freeze":
        from .cases import load_cases
        from .runner import FROZEN, config_hash
        frozen = json.loads(FROZEN.read_text()) if FROZEN.exists() else {"systems": {}}
        _, digest = load_cases("heldout")
        frozen["cases_sha256"] = digest
        for name in args.systems:
            frozen["systems"][name] = config_hash(known[name])
        FROZEN.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
        print(json.dumps(frozen, indent=2))
    elif args.command == "train-data":
        from .train_data import generate
        generate(args.per_template, ceiling_usd=args.max_usd)
    elif args.command == "train-split":
        from .train_data import split_for_training
        print(split_for_training())
    elif args.command == "train-router":
        from .router import train
        print(json.dumps(train(), indent=2))
    elif args.command == "cascades":
        from .router import write_cascades
        print(json.dumps(write_cascades(args.split), indent=2))


if __name__ == "__main__":
    main()
