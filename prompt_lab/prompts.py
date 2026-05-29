"""Load a prompt variant file (## system / ## user sections) and render the user template."""
import os
from dataclasses import dataclass


@dataclass
class PromptVariant:
    id: str
    system: str
    user_template: str


def load_variant(path: str) -> PromptVariant:
    text = open(path, encoding="utf-8").read()
    sections = {"system": [], "user": []}
    current = None
    for line in text.splitlines():
        header = line.strip().lower()
        if header == "## system":
            current = "system"
            continue
        if header == "## user":
            current = "user"
            continue
        if current:
            sections[current].append(line)
    variant_id = os.path.splitext(os.path.basename(path))[0]
    return PromptVariant(
        id=variant_id,
        system="\n".join(sections["system"]).strip(),
        user_template="\n".join(sections["user"]).strip(),
    )


def render_user(variant: PromptVariant, case: dict) -> str:
    return variant.user_template.format(**case)
