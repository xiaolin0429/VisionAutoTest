from __future__ import annotations

from decimal import Decimal
from urllib.parse import urljoin, urlparse


def payload_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Step payload `{key}` is required.")
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    raise ValueError(f"Step payload `{key}` must be numeric.")


def payload_float(payload: dict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Step payload `{key}` is required.")
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    raise ValueError(f"Step payload `{key}` must be numeric.")


def payload_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Step payload `{key}` must be a non-empty string.")
    return value


def resolve_navigate_url(base_url: str, url: str) -> str:
    if url.startswith("/"):
        return urljoin(base_url, url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            "navigate `url` must be an absolute http/https URL or a path starting with `/`."
        )
    return url


def scroll_delta(direction: str, distance: float) -> tuple[float, float]:
    if direction == "up":
        return 0.0, -distance
    if direction == "down":
        return 0.0, distance
    if direction == "left":
        return -distance, 0.0
    if direction == "right":
        return distance, 0.0
    raise ValueError("scroll `direction` must be `up`, `down`, `left`, or `right`.")


def settle_scroll(page, behavior: str) -> None:
    page.wait_for_timeout(50)
    if behavior == "smooth":
        page.wait_for_timeout(250)


def optional_positive_int(payload: dict, key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"Step payload `{key}` must be numeric.")
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"Step payload `{key}` must be greater than 0.")
    return parsed


def optional_non_negative_int(payload: dict, key: str, *, default: int) -> int:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"Step payload `{key}` must be numeric.")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"Step payload `{key}` must be greater than or equal to 0.")
    return parsed


def optional_ratio(payload: dict, key: str, *, default: float) -> float:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"Step payload `{key}` must be numeric.")
    parsed = float(value)
    if parsed < 0 or parsed > 1:
        raise ValueError(f"Step payload `{key}` must be between 0 and 1.")
    return parsed


def input_via_keyboard(
    page,
    *,
    text: str,
    input_mode: str,
    otp_length: int | None,
    per_char_delay_ms: int,
) -> None:
    if input_mode == "fill":
        page.keyboard.type(text)
        return

    if input_mode == "type":
        page.keyboard.type(text, delay=per_char_delay_ms)
        return

    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("input `text` must be a non-empty string.")
    expected_length = otp_length if otp_length is not None else len(normalized_text)
    if len(normalized_text) != expected_length:
        raise ValueError("input `text` length must match `otp_length` in otp mode.")

    for char in normalized_text:
        page.keyboard.insert_text(char)
        page.wait_for_timeout(per_char_delay_ms)


def prepare_input_focus(page, *, input_mode: str) -> None:
    if input_mode != "otp":
        return

    focused = page.evaluate(
        """() => {
            const inputs = Array.from(document.querySelectorAll('input.base-code-box-input'));
            const firstVisible = inputs.find((item) => {
                if (!(item instanceof HTMLInputElement)) return false;
                const rect = item.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && !item.disabled;
            });
            if (!(firstVisible instanceof HTMLInputElement)) {
                return false;
            }
            firstVisible.focus();
            firstVisible.click();
            return document.activeElement === firstVisible;
        }"""
    )
    if focused:
        page.wait_for_timeout(100)


def verify_input_applied(
    page,
    *,
    text: str,
    input_mode: str,
    otp_length: int | None,
) -> None:
    if input_mode == "fill":
        return

    if input_mode == "otp":
        expected_length = otp_length if otp_length is not None else len(text)
        otp_state = page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input.base-code-box-input'));
                return inputs.map((item) => ({ value: item.value || '' }));
            }"""
        )
        if isinstance(otp_state, list) and otp_state:
            joined = "".join(str(item.get("value", "")) for item in otp_state)
            if len(joined) == expected_length and joined == text:
                return
            raise RuntimeError(
                "OTP input did not populate verification boxes with the expected value."
            )

    active_value = page.evaluate(
        """() => {
            const active = document.activeElement;
            if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
                return active.value || '';
            }
            return '';
        }"""
    )
    if active_value != text:
        raise RuntimeError("Keyboard input did not persist the expected value.")
