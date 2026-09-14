"""Gemini token prices, and what one call cost.

Its own module, stdlib only, because two processes need it: `gemini_client`
writes `cost_usd` onto every logged call, and `work/worker/vma_worker.py` reads
those logs back to enforce a per-job budget. Importing `gemini_client` from the
worker would drag in PIL and google.genai for the sake of three numbers.

The rates themselves live in `work/ocr/prices.json`, not here, because
`scripts/enqueue_ocr_all.mjs` needs the same numbers in JavaScript to estimate
a sweep before it is queued. One file read by both beats a copy in each, which
would be a duplicated signal needing a parity test to stay honest.
"""

from __future__ import annotations

import json
from pathlib import Path

_PRICES_PATH = Path(__file__).resolve().parent.parent / "prices.json"


def _load_prices() -> dict[str, dict[str, float]]:
    """Rates from prices.json. A missing or malformed file prices nothing.

    Returning {} rather than raising is deliberate: an unreadable price file
    must not stop a pipeline run, it must make every cost come back None so
    the gap is visible in the logs and in `_spend`'s `unpriced_calls`.
    """
    try:
        return json.loads(_PRICES_PATH.read_text())["models"]
    except (OSError, ValueError, KeyError):
        return {}


PRICES: dict[str, dict[str, float]] = _load_prices()


def call_cost_usd(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    cached_tokens: int | None,
) -> float | None:
    """USD for one call, or None when the model has no published rate.

    Billed output is taken as `total - input` — candidates plus thinking —
    which is what `docs/pipelines.md` §Cost concluded on 2026-09-10. That
    conclusion was inferred from token counts and has never been checked
    against an invoice; if it is wrong, every figure derived from this is
    about 2.5x too high. Settling it needs no new data collection, because
    the raw fields are logged beside this number: compare a billing export's
    output-token SKU quantity against the sum of `output_tokens` versus the
    sum of `total_tokens - input_tokens`.

    `output_tokens` is unused in the arithmetic and is taken only to keep the
    call sites honest about which four numbers the answer depends on.
    """
    rate = PRICES.get(model or "")
    if not rate or total_tokens is None or input_tokens is None:
        return None
    cached = cached_tokens or 0
    fresh_in = max(input_tokens - cached, 0)
    billed_out = max(total_tokens - input_tokens, 0)
    return round(
        fresh_in * rate["input"] / 1e6
        + cached * rate["cached"] / 1e6
        + billed_out * rate["output"] / 1e6,
        6,
    )
