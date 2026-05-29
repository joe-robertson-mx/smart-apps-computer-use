import glob
from prompt_lab.prompts import load_variant, render_user
from prompt_lab.scenarios import load_scenario


def test_all_sample_prompts_load():
    files = glob.glob("prompt_lab/prompts/*.md")
    assert files
    for f in files:
        v = load_variant(f)
        assert v.system and v.user_template


def test_all_sample_scenarios_load_and_render():
    files = glob.glob("prompt_lab/scenarios/*.yaml")
    assert files
    for f in files:
        s = load_scenario(f)
        assert s.mode in {"single_prompt", "conversational"}
        assert s.target in {"warranty", "returns"}


def test_warranty_variant_renders_against_scenario_case():
    v = load_variant("prompt_lab/prompts/warranty_v1.md")
    s = load_scenario("prompt_lab/scenarios/warranty-wheel-replacement.yaml")
    rendered = render_user(v, s.case)
    assert rendered  # no missing placeholders -> no KeyError
