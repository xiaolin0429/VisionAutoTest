from __future__ import annotations

from app.workers.browser_step_handlers import (
    execute_click,
    execute_conditional_branch,
    execute_input,
    execute_long_press,
    execute_navigate,
    execute_ocr_assert,
    execute_scroll,
    execute_template_assert,
    execute_wait,
)


STEP_HANDLER_REGISTRY = {
    "wait": execute_wait,
    "click": execute_click,
    "input": execute_input,
    "navigate": execute_navigate,
    "scroll": execute_scroll,
    "long_press": execute_long_press,
    "conditional_branch": execute_conditional_branch,
    "ocr_assert": execute_ocr_assert,
    "template_assert": execute_template_assert,
}


def get_step_handler(step_type: str):
    return STEP_HANDLER_REGISTRY.get(step_type)
