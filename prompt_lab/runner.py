"""Run the {variant × scenario × model × repeat} matrix and produce scored cells.

Clients (bedrock/executor/control) are injected so this is unit-testable; the CLI
wires the real BedrockClient/ExecutorClient/ControlClient.
"""
import argparse
import glob
import os
import time

from prompt_lab import report
from prompt_lab.bedrock_loop import run_episode
from prompt_lab.drivers.persona import PersonaDriver
from prompt_lab.drivers.scripted import ScriptedDriver
from prompt_lab.models import spec_for
from prompt_lab.prompts import PromptVariant, load_variant, render_user
from prompt_lab.scenarios import Scenario, load_scenario
from prompt_lab.scoring import score

STEP_CAP = int(os.getenv("PROMPT_LAB_STEP_CAP", "30"))


def _run_cell(variant, scenario, spec, bedrock, executor, control, persona_complete):
    setup = control.setup(scenario.target, scenario.case)
    baseline = setup.get("baseline_count", 0)
    time.sleep(float(os.getenv("PROMPT_LAB_SETTLE", "3")))  # let the app relaunch/settle
    user_prompt = render_user(variant, scenario.case)

    driver = None
    if scenario.mode == "conversational":
        if scenario.script:
            driver = ScriptedDriver(scenario.script)
        else:
            driver = PersonaDriver(goal=scenario.goal or "", complete=persona_complete,
                                   max_turns=scenario.max_user_prompts or 6)

    transcript = run_episode(bedrock, executor, spec, system=variant.system,
                             user_prompt=user_prompt, step_cap=STEP_CAP,
                             driver=driver, max_user_prompts=scenario.max_user_prompts)

    after = control.records(scenario.target).get("records", [])
    new_records = after[baseline:]
    result = score(scenario, new_records, transcript, step_cap=STEP_CAP,
                   max_user_prompts=scenario.max_user_prompts)
    return {
        "variant": variant.id, "scenario": scenario.id, "model": spec.key,
        "passed": result.passed, "reasons": result.reasons,
        "steps": result.metrics["steps"], "cost": transcript.cost(spec),
        "metrics": result.metrics,
    }


def run_matrix(variants, scenarios, model_keys, repeats, bedrock, executor, control,
               persona_complete) -> list[dict]:
    cells = []
    for variant in variants:
        for scenario in scenarios:
            for model_key in model_keys:
                spec = spec_for(model_key)
                for _ in range(repeats):
                    try:
                        cells.append(_run_cell(variant, scenario, spec, bedrock, executor,
                                               control, persona_complete))
                    except Exception as exc:  # keep the matrix going if one episode dies
                        cells.append({"variant": variant.id, "scenario": scenario.id,
                                      "model": spec.key, "passed": False,
                                      "reasons": [f"episode error: {exc}"],
                                      "steps": 0, "cost": 0.0, "metrics": {}})
    return cells


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the computer-use prompt lab matrix.")
    parser.add_argument("--host", required=True, help="executor+control base URL, e.g. http://3.249.25.226:8081")
    parser.add_argument("--prompts", default="prompt_lab/prompts/*.md")
    parser.add_argument("--scenarios", default="prompt_lab/scenarios/*.yaml")
    parser.add_argument("--models", default="sonnet-4-5", help="comma-separated model keys")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--region", default="eu-west-1")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--out", default="prompt_lab/reports")
    args = parser.parse_args(argv)

    from prompt_lab.bedrock_client import BedrockClient
    from prompt_lab.control_client import ControlClient
    from prompt_lab.executor_client import ExecutorClient

    variants = [load_variant(p) for p in sorted(glob.glob(args.prompts))]
    scenarios = [load_scenario(p) for p in sorted(glob.glob(args.scenarios))]
    bedrock = BedrockClient(region=args.region, profile=args.profile)
    executor = ExecutorClient(args.host)
    control = ControlClient(args.host)
    persona_spec = spec_for(args.models.split(",")[0].strip())
    persona_complete = lambda system, user: bedrock.complete_text(persona_spec, system, user)

    cells = run_matrix(variants, scenarios, [m.strip() for m in args.models.split(",")],
                       args.repeats, bedrock, executor, control, persona_complete)
    paths = report.write(cells, args.out)
    print(f"Report: {paths['markdown']}")


if __name__ == "__main__":
    main()
