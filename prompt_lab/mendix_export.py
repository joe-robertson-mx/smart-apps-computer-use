"""Emit the chosen prompts as paste-ready Mendix TestSystemPrompt / TestUserPrompt values."""
from prompt_lab.prompts import PromptVariant, render_user


def export_variant(variant: PromptVariant, case: dict) -> str:
    user = render_user(variant, case)
    return (
        f"# Variant: {variant.id}\n\n"
        "## EnquiryManagementMemory.TestSystemPrompt\n"
        f"{variant.system}\n\n"
        "## EnquiryManagementMemory.TestUserPrompt\n"
        f"{user}\n"
    )
