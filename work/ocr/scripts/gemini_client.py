"""Gemini API wrapper for the OCR pipeline."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

# Lazy import — only needed when actually calling the API
try:
    import google.genai as genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Default model — run `ocr.py list-models` to verify this is current.
#
# Was `gemini-3-flash-preview` until 2026-09-04. That name still answers, but it
# is absent from Google's pricing page entirely, which is what a preview looks
# like on its way out: no published rate, no stated support window. 3.8-flash is
# the current Flash line at $0.75/$3.75 per 1M in/out — measured against this
# corpus at ~30-60 calls per sheet, that is roughly $0.85-1.65 a map.
#
# That was "$0.50 a map" until 2026-09-10, computed from the `output_tokens`
# this module logs below. Billed output is `total_tokens - input_tokens` and
# includes thinking, which on a measured run is 3.5x the logged field. The
# 1968 body pass was 48 calls at $1.236.
DEFAULT_MODEL = "gemini-3.8-flash"


def _load_keys() -> list[str]:
    """Return all available API keys. GEMINI_API_KEYS (comma-separated) takes priority."""
    from dotenv import load_dotenv
    # Explicit path so this works regardless of CWD (e.g. background nohup calls)
    _repo_root = Path(__file__).resolve().parents[3]
    load_dotenv(_repo_root / ".env")
    multi = os.environ.get("GEMINI_API_KEYS", "")
    if multi:
        return [k.strip() for k in multi.split(",") if k.strip()]
    single = os.environ.get("GEMINI_API_KEY", "")
    if single:
        return [single]
    raise EnvironmentError("Set GEMINI_API_KEY or GEMINI_API_KEYS in .env")


# Module-level key index so rotation persists across calls within one process
_key_index = 0
_key_lock = threading.Lock()
_log_lock = threading.Lock()


def _load_client() -> tuple[Any, str]:
    """Return (client, active_key). Starts from current _key_index."""
    if not GENAI_AVAILABLE:
        raise ImportError("google-genai not installed. Run: pip install google-genai")
    keys = _load_keys()
    with _key_lock:
        key = keys[_key_index % len(keys)]
    return genai.Client(api_key=key), key


def _rotate_key() -> bool:
    """Advance to next key. Returns False if we've cycled through all keys."""
    global _key_index
    keys = _load_keys()
    with _key_lock:
        _key_index += 1
        exhausted = _key_index >= len(keys)
        idx = _key_index
    if exhausted:
        return False
    print(f"\n  Rotating to key {idx + 1}/{len(keys)} ...", flush=True)
    return True


# ── Explicit context cache ────────────────────────────────────────────────────
# Implicit caching never hit on gemini-3-flash-preview in a 3-call sample, even
# with the prompt as a byte-identical prefix. Explicit caching is deterministic:
# system prompt + task prompt go into one cached content per (key, model, text),
# and each call sends only its images against it. Set GEMINI_EXPLICIT_CACHE=0
# to fall back to inline prompts. Create failures (prompt under the model's
# minimum, unsupported model) are remembered per process so one failed prefix
# costs one extra round-trip, not one per tile.
_prefix_cache: dict[tuple, str | None] = {}
_prefix_lock = threading.Lock()


def _cached_prefix(client: Any, key: str, model: str, system_prompt: str, prompt: str) -> str | None:
    if os.environ.get("GEMINI_EXPLICIT_CACHE", "1") == "0":
        return None
    k = (key, model, system_prompt, prompt)
    with _prefix_lock:
        if k in _prefix_cache:
            return _prefix_cache[k]
    name: str | None
    try:
        cc = client.caches.create(
            model=model,
            config=genai_types.CreateCachedContentConfig(
                system_instruction=system_prompt,
                contents=[prompt],
                ttl="3600s",
                display_name="vma-ocr-prefix",
            ),
        )
        name = cc.name
    except Exception as e:
        print(f"  explicit cache unavailable ({str(e)[:90]}); sending prompt inline", flush=True)
        name = None
    with _prefix_lock:
        _prefix_cache[k] = name
    return name


def _with_prefix(config_kwargs: dict, cache_name: str | None) -> dict:
    """GenerateContentConfig kwargs for a call against a cached prefix (or not)."""
    if not cache_name:
        return config_kwargs
    cfg = {k: v for k, v in config_kwargs.items() if k != "system_instruction"}
    cfg["cached_content"] = cache_name
    return cfg


def _parse_response_text(text: str) -> dict:
    """Extract JSON from response text, handling thinking-mode preambles."""
    text = text.strip()

    # Strip <thinking>...</thinking> blocks if present
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()

    # Find the first JSON object
    match = re.search(r"\{", text)
    if match:
        text = text[match.start():]

    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def _log_malformed(log_path: Path | None, raw_text: str, model: str, context: str = "") -> None:
    """Append a malformed-JSON incident to malformed.jsonl beside calls.jsonl."""
    if not log_path:
        return
    malformed_path = log_path.parent / "malformed.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "context": context,
        "raw_text_snippet": raw_text[:500],
    }
    with _log_lock:
        with open(malformed_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def _parse_result(response_text: str, schema: dict, model: str, user_prompt: str,
                  config_kwargs: dict, client: Any, log_path: Path | None,
                  context: str = "", image_parts: list | None = None) -> dict:
    """Parse JSON from response text; retry once with schema hint on failure.

    image_parts: the image Part(s) from the original call. Must be re-sent on
    retry — a text-only retry gives the model nothing to read (it would
    hallucinate or return empty extractions).
    """
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    try:
        return _parse_response_text(response_text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Both parse attempts failed — log and retry once with an explicit schema reminder
    _log_malformed(log_path, response_text, model, context)
    print(f"\n  Malformed JSON ({context}) — retrying with schema hint ...", flush=True)
    schema_hint = (
        "\n\nIMPORTANT: Your previous response was not valid JSON. "
        "Return ONLY a valid JSON object with this exact structure:\n"
        '{"extractions": [{"text": "...", "category": "...", "language": "...", '
        '"bbox_px": [x, y, w, h], "rotation_deg": 0, "confidence": 0.9}]}\n'
        "bbox_px is [x, y, width, height] in 0-1000 normalized scale "
        "(0,0 = top-left, 1000,1000 = bottom-right of the frame)."
    )
    retry_prompt = user_prompt + schema_hint if isinstance(user_prompt, str) else schema_hint
    retry_response = client.models.generate_content(
        model=model,
        contents=(image_parts or []) + [retry_prompt],
        config=genai_types.GenerateContentConfig(**config_kwargs),
    )
    try:
        return json.loads(retry_response.text)
    except json.JSONDecodeError:
        return _parse_response_text(retry_response.text)


# How many times one call may be retried before it gives up.
#
# The loops below used to be unbounded `while True`: a persistently rate-limited
# or 5xx endpoint retried every two minutes forever, and because the worker runs
# these under a subprocess with no timeout and nothing reclaimed a stranded job,
# one bad afternoon at the API wedged a worker and a map together. Backoff caps
# at 120s, so 12 attempts is a little over 20 minutes of trying — long enough to
# ride out a real rate-limit episode, short enough that the job fails, gets
# requeued by finish_job and can be picked up by a worker that is not stuck.
#
# Key rotation on true quota exhaustion is deliberately *not* counted: rotating
# to a fresh key is progress, not a retry, and the loop already ends when the
# keys run out.
MAX_CALL_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "12"))


def _has_status(err_str: str, *codes: str) -> bool:
    """True when the error text carries one of these HTTP status codes.

    Matched as a standalone number, not a substring: plain `"500" in err_str`
    also fires on a token count of 1500 or a byte offset of 25000, and with a
    retry budget in place a misread permanent error now costs twelve backoffs
    per tile rather than one immediate failure.
    """
    import re as _re2
    return any(_re2.search(rf"(?<!\d){c}(?!\d)", err_str) for c in codes)


def extract_labels(
    image: Image.Image,
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    model: str = DEFAULT_MODEL,
    thinking: bool = True,
    log_path: Path | None = None,
    cache_dir: Path | None = None,
) -> dict:
    """Call Gemini to extract text labels from a map tile image.

    Returns the parsed JSON response dict.
    Logs token usage + latency to log_path (JSONL) if provided.
    Caches result by content hash in cache_dir (skips API call on hit).

    Rate-limit handling:
    - 200ms stagger before every call (smooths burst spikes at concurrency > 1)
    - Exponential backoff on 429 rate-limit: 2s → 4s → 8s … up to 120s
    - True quota exhaustion (credits depleted / daily RPD) → key rotation
    - 503/500 transient → fixed 30s wait
    - Malformed JSON → one retry with schema hint; logs to malformed.jsonl
    """
    import io, re as _re
    from cache import get as cache_get, put as cache_put, schema_version

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=90)
    image_bytes = buf.getvalue()

    # Cache hit — free result, no API call
    sv = schema_version(schema)
    cached = cache_get(image_bytes, user_prompt, model, cache_dir=cache_dir,
                       schema_version=sv)
    if cached is not None:
        return cached

    config_kwargs: dict[str, Any] = {
        "system_instruction": system_prompt,
        "response_mime_type": "application/json",
        "response_schema": schema,
        # A dense tile can hold 100+ labels; the model default output cap
        # truncates mid-JSON (the "unterminated string" malformed error). Give
        # it plenty of headroom so a full tile never gets cut off.
        "max_output_tokens": 65536,
    }

    # `thinking=False` asks for the minimal level rather than a budget: the
    # segmentation docs recommend it, and on a mask call thinking spends output
    # tokens re-deriving a polygon it has already committed to. Left on by
    # default, because every text path measured so far is better with it.
    #
    # ponytail: the cache key does not include this. Two runs of one tile that
    # differ only here collide, so set it per run rather than to A/B it. Fold it
    # into `schema_version` if that ever has to be an experiment.
    if not thinking:
        # "low", not the "minimal" the segmentation docs name: gemini-3.8-flash
        # answers MINIMAL with `400 INVALID_ARGUMENT. Thinking level MINIMAL is
        # not supported for this model`, so the doc's advice cannot be followed
        # literally on the model this pipeline runs.
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_level="low"
        )

    # Small stagger before every call to smooth per-second burst spikes.
    # Default 200ms; override with GEMINI_CALL_DELAY_S env var.
    call_delay = float(os.environ.get("GEMINI_CALL_DELAY_S", "0.2"))
    time.sleep(call_delay)

    t_start = time.monotonic()
    backoff = 2.0  # starting backoff for rate-limit retries (doubles each attempt)
    retries = 0

    while True:
        client, active_key = _load_client()
        try:
            image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            prefix = _cached_prefix(client, active_key, model, system_prompt, user_prompt)
            response = client.models.generate_content(
                model=model,
                # Prompt first, image last: the prompt is the stable prefix,
                # served from the explicit cache when one could be created.
                contents=[image_part] if prefix else [user_prompt, image_part],
                config=genai_types.GenerateContentConfig(**_with_prefix(config_kwargs, prefix)),
            )
            elapsed = time.monotonic() - t_start
            result = _parse_result(
                response.text, schema, model, user_prompt, config_kwargs, client,
                log_path, context="extract_labels",
                image_parts=[genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
            )
            if log_path:
                _log_call(log_path=log_path, model=model, elapsed=elapsed,
                          usage=response.usage_metadata,
                          n_extractions=len(result.get("extractions", [])))
            cache_put(image_bytes, user_prompt, model, result, cache_dir=cache_dir,
                      schema_version=sv)
            return result

        except Exception as e:
            err_str = str(e)

            # True quota exhaustion: daily RPD or prepayment credits gone.
            # Distinct from per-second/per-minute rate limits.
            is_true_quota = (
                "credits are depleted" in err_str.lower()
                or "prepayment" in err_str.lower()
                or ("RESOURCE_EXHAUSTED" in err_str and "429" not in err_str)
            )
            # A spending cap is not a rate limit: waiting cannot clear it, and no
            # other key on the same project will either. It arrives as a 429
            # RESOURCE_EXHAUSTED, so without this it read as a per-minute limit
            # and every call spent the full backoff ladder — about fourteen
            # minutes each, a fleet of tiles quietly reporting "rate limited"
            # for hours against a wall that needs a human at
            # https://ai.studio/spend.
            if "spending cap" in err_str.lower() or "spend cap" in err_str.lower():
                raise RuntimeError(
                    "Gemini project spending cap reached — raise it at "
                    "https://ai.studio/spend, then re-run. Nothing was lost: "
                    "every band already read is cached."
                ) from e
            # Per-second or per-minute rate limit — back off and retry same key.
            is_rate = _has_status(err_str, "429") and not is_true_quota
            is_transient = _has_status(err_str, "503", "500") or "UNAVAILABLE" in err_str

            if is_true_quota:
                if not _rotate_key():
                    raise RuntimeError("All API keys exhausted for today") from e
                backoff = 2.0  # reset backoff after key rotation
                continue

            if is_rate or is_transient:
                retries += 1
                if retries > MAX_CALL_RETRIES:
                    raise RuntimeError(
                        f"gave up after {MAX_CALL_RETRIES} retries on: {err_str[:200]}"
                    ) from e
                if is_rate:
                    # Honour Retry-After header if present, else exponential backoff.
                    m = _re.search(r"retry[_\s-]?after[:\s]+([\d.]+)", err_str, _re.IGNORECASE)
                    wait = float(m.group(1)) + 1 if m else backoff
                    backoff = min(backoff * 2, 120.0)
                    print(f"\n  Rate limited — waiting {wait:.0f}s "
                          f"(next backoff {backoff:.0f}s, retry {retries}/{MAX_CALL_RETRIES}) ...",
                          flush=True)
                else:
                    wait = 30.0
                    print(f"\n  Model unavailable — waiting 30s "
                          f"(retry {retries}/{MAX_CALL_RETRIES}) ...", flush=True)
                time.sleep(wait)
                continue

            raise


def _log_call(
    log_path: Path,
    model: str,
    elapsed: float,
    usage: Any,
    n_extractions: int,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "elapsed_s": round(elapsed, 2),
        "n_extractions": n_extractions,
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
        # Non-zero only when the prompt-first ordering hit the implicit cache.
        "cached_tokens": getattr(usage, "cached_content_token_count", None),
    }
    with _log_lock:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def extract_labels_sequence(
    images: list[Image.Image],
    system_prompt: str,
    schema: dict,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    thinking: bool = True,
    log_path: Path | None = None,
    cache_dir: Path | None = None,
) -> dict:
    """Send a sequence of overlapping tile images in ONE call (MapSAM2-style).

    The model sees all tiles as adjacent frames and can assemble labels that
    span tile boundaries — solving the seam problem at the model level.

    Returns extractions with a 'frame_idx' field indicating which tile the
    bbox coordinates belong to (0-indexed).

    `user_prompt` is required, and is the whole task prompt: the caller composes the
    prompt version it selected with the frame rules that suit its own frames
    (`prompt.sequence_frame_rules()` for adjacent tiles; `cmd_scout` writes its own,
    because it sends the *same map at several resolutions* rather than a tile row).

    It has no default on purpose. There used to be one, naming an "1882 Saigon
    cadastral map", and every caller that forgot to pass a prompt silently got that
    instead of the prompt the run asked for — which is exactly what `cmd_batch` did
    on the production path until 2026-09-08. A missing prompt is now a TypeError.
    """
    import io, re as _re
    from cache import get as cache_get, put as cache_put, schema_version

    parts = []
    all_image_bytes: list[bytes] = []
    for i, image in enumerate(images):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90)
        img_bytes = buf.getvalue()
        all_image_bytes.append(img_bytes)
        parts.append(
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        )
        parts.append(f"[Frame {i}]")

    sequence_prompt = user_prompt

    # Cache key covers all image bytes + the sequence prompt + model
    cache_key_bytes = b"".join(all_image_bytes)
    # The thinking level changes the answer, so it has to change the key. Its
    # absence from `extract_labels`' key is a known trap (see the ponytail note
    # there): an A/B in one cache_dir silently replays the first run's answers.
    sv = schema_version(schema) + ("" if thinking else "+lowthink")
    cached = cache_get(cache_key_bytes, sequence_prompt, model, cache_dir=cache_dir,
                       schema_version=sv)
    if cached is not None:
        return cached

    # Extend schema to include frame_idx, keeping every other property the
    # caller declared. Rebuilding it with only `extractions` — as this did until
    # 2026-09-04 — silently drops SCOUT_SCHEMA's `regions`, `map_content_bbox`,
    # `cartouche_bbox` and `metadata`, so the model has no slot to answer in and
    # the layout pass can never return anything.
    seq_schema = {
        **schema,
        "properties": {
            **schema["properties"],
            "extractions": {
                "type": "array",
                "items": {
                    **schema["properties"]["extractions"]["items"],
                    "properties": {
                        **schema["properties"]["extractions"]["items"]["properties"],
                        "frame_idx": {"type": "integer"},
                    },
                },
            },
        },
    }

    config_kwargs: dict = {
        "system_instruction": system_prompt,
        "response_mime_type": "application/json",
        "response_schema": seq_schema,
        # Same truncation guard as extract_labels: a dense row-strip holds 100+
        # labels and the default output cap cuts JSON mid-string ("unterminated
        # string" malformed error). This is the default batch path, and the
        # malformed retry inherits config_kwargs — without the cap it would
        # truncate again on the retry too.
        "max_output_tokens": 65536,
    }

    # Measured 2026-09-12 on the numeral pass: thinking was 93% of billed output
    # and turning it down was both 3.4x cheaper AND more accurate (126/182 vs
    # 116). On the 1878 body pass it is 54% of the bill. See EVAL-BASELINE.
    # "low", not "minimal" — this model rejects MINIMAL outright.
    if not thinking:
        config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_level="low"
        )

    t_start = time.monotonic()
    backoff = 2.0
    retries = 0

    while True:
        client, active_key = _load_client()
        try:
            prefix = _cached_prefix(client, active_key, model, system_prompt, sequence_prompt)
            response = client.models.generate_content(
                model=model,
                # Prompt first: see extract_labels.
                contents=parts if prefix else [sequence_prompt] + parts,
                config=genai_types.GenerateContentConfig(**_with_prefix(config_kwargs, prefix)),
            )
            elapsed = time.monotonic() - t_start
            result = _parse_result(
                response.text, seq_schema, model, sequence_prompt, config_kwargs, client,
                log_path, context="extract_labels_sequence",
                image_parts=parts,
            )
            if log_path:
                _log_call(log_path=log_path, model=model, elapsed=elapsed,
                          usage=response.usage_metadata,
                          n_extractions=len(result.get("extractions", [])))
            cache_put(cache_key_bytes, sequence_prompt, model, result, cache_dir=cache_dir,
                      schema_version=sv)
            return result
        except Exception as e:
            err_str = str(e)
            is_quota = "EXHAUSTED" in err_str.upper() or (
                _has_status(err_str, "429") and "quota" in err_str.lower())
            is_rate  = _has_status(err_str, "429") and not is_quota
            is_transient = _has_status(err_str, "503", "500") or "UNAVAILABLE" in err_str
            if is_quota:
                if not _rotate_key():
                    raise RuntimeError("All API keys exhausted for today") from e
                backoff = 2.0
                continue
            if is_rate or is_transient:
                retries += 1
                if retries > MAX_CALL_RETRIES:
                    raise RuntimeError(
                        f"gave up after {MAX_CALL_RETRIES} retries on: {err_str[:200]}"
                    ) from e
                if is_rate:
                    m = _re.search(r"retry in ([\d.]+)s", err_str, _re.IGNORECASE)
                    wait = float(m.group(1)) + 2 if m else backoff
                    backoff = min(backoff * 2, 120.0)
                    print(f"\n  Rate limited — waiting {wait:.0f}s "
                          f"(retry {retries}/{MAX_CALL_RETRIES}) ...", flush=True)
                else:
                    wait = 30.0
                    print(f"\n  Model unavailable — waiting 30s "
                          f"(retry {retries}/{MAX_CALL_RETRIES}) ...", flush=True)
                time.sleep(wait)
                continue
            raise


def list_models() -> list[str]:
    """Return available Gemini model IDs (useful for verifying thinking model name)."""
    client, _ = _load_client()
    models = client.models.list()
    return sorted(m.name for m in models)


# ── Legend extraction (structured numbered-legend read) ────────────────────────

_LEGEND_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "name": {"type": "string"},
                    "name_vn": {"type": "string"},
                    "grid": {"type": "string"},
                },
                "required": ["n", "name", "grid"],
            },
        }
    },
    "required": ["entries"],
}


_STREET_INDEX_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "generic": {"type": "string"},
                    "name": {"type": "string"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["generic", "name", "from", "to"],
            },
        }
    },
    "required": ["entries"],
}


_GRID_SCHEMA = {
    "type": "object",
    "properties": {
        "bbox": {
            "type": "array",
            "items": {"type": "number"},
            "description": "[x, y, width, height] of the gridded area on a 0-1000 scale.",
        },
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["bbox", "columns", "rows"],
}


def extract_grid(image: Image.Image, model: str = DEFAULT_MODEL) -> dict:
    """Read a sheet's printed reference grid as {bbox, columns, rows}.

    The labels are returned as printed rather than as an A-Z range on purpose:
    sheets skip `I` to keep it apart from `1`, start at `0`, or run past `Z`.
    Deriving the sequence instead of reading it puts every later column one cell
    out, which on a city sheet is a few hundred metres and looks perfectly
    plausible on the map.
    """
    from io import BytesIO
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92)
    image_bytes = buf.getvalue()

    prompt = (
        "This is a historical map sheet carrying a printed reference grid — the "
        "ruled squares an index refers to with codes like 'J 6'.\n\n"
        "Return three things.\n"
        "1. `bbox`: the gridded area, [x, y, width, height] on a 0-1000 normalized "
        "scale. Its edges are the OUTER edges of the outermost cells, not the "
        "neatline and not the paper.\n"
        "2. `columns`: every column label, left to right, exactly as printed in the "
        "margin.\n"
        "3. `rows`: every row label, top to bottom, exactly as printed.\n\n"
        "Read the labels off the sheet. Do NOT assume they run A, B, C… — many "
        "sheets skip the letter I so it cannot be confused with the digit 1, and "
        "some begin at 0. Report exactly the sequence printed, including any gap. "
        "If the sheet has no reference grid, return an empty `columns` and `rows`."
    )

    client, _ = _load_client()
    config = genai_types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        response_schema=_GRID_SCHEMA,
    )
    resp = client.models.generate_content(
        model=model,
        contents=[genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
        config=config,
    )
    import json as _json
    return _json.loads(resp.text)


_STREET_INDEX_PROMPT = (
    "This is a printed street directory (BẢNG CHỈ DẪN ĐƯỜNG PHỐ) from a "
    "Vietnamese map of Saigon. It is a four-column table, one row per street:\n"
    "  1. the road-type word alone (Đường, Đại Lộ, Bến, Rạch, Hẻm, Kinh, Ngõ)\n"
    "  2. the street name\n"
    "  3. TỪ — the grid cell the street starts in: a letter then a number\n"
    "  4. ĐẾN — the grid cell it ends in\n\n"
    "Read EVERY row, top to bottom, including any partial row at the very top or "
    "bottom of the image. Return generic, name, from, to.\n\n"
    "Keep Vietnamese diacritics exactly as printed, and keep the two grid cells "
    "in their own fields — do not merge them. The cells are printed in a lighter "
    "ink than the names; read the letter and the number carefully and do not "
    "infer either from the row above. A row whose two cells are the same is "
    "normal. Give each cell as letter then number with no space, e.g. 'C10'."
)

_STREET_INDEX_SYSTEM = (
    "You transcribe printed tables from historical maps. Return only what is "
    "printed. Never invent a row to fill a gap and never carry a value down "
    "from the row above: a blank is a blank."
)


def extract_street_index(image: Image.Image, model: str = DEFAULT_MODEL,
                         log_path: Path | None = None,
                         cache_dir: Path | None = None) -> list[dict]:
    """Read a printed street directory as [{generic, name, from, to}].

    Not the same table as `extract_legend`: a street directory has no numbers —
    it is alphabetical, and each row states the grid cell where the street
    starts and the one where it ends ("TỪ" / "ĐẾN"). That pair is a run of
    cells, which locates a street far better than the single cell a numbered
    legend gives, and the sheet prints it for every street it names.

    `generic` is the road-type word from its own column (Đường, Đại Lộ, Bến,
    Rạch, Hẻm, Kinh), kept apart from `name` so the caller can choose a category
    without parsing it back out of the label.

    Goes through `extract_labels` rather than calling the model directly, which
    is what `extract_legend` does: that buys the 429 backoff, the key rotation,
    the malformed-JSON retry, the token log and — reading a directory in a dozen
    overlapping bands — the content cache, so a re-run of the same bands is
    free. A raw call has none of it, and a rate limit mid-run drops a band of
    thirty streets while the run still reports success.
    """
    data = extract_labels(
        image,
        system_prompt=_STREET_INDEX_SYSTEM,
        user_prompt=_STREET_INDEX_PROMPT,
        schema=_STREET_INDEX_SCHEMA,
        model=model,
        log_path=log_path,
        cache_dir=cache_dir,
    )
    return data.get("entries", [])


def extract_legend(image: Image.Image, model: str = DEFAULT_MODEL,
                   bilingual: bool = False) -> list[dict]:
    """Extract a numbered map legend as [{n, name, name_vn?, grid}].

    Forces JSON via response_schema, so the return is always valid structured
    data. `bilingual` tells the model the rows carry both a Vietnamese and an
    English name (name_vn = Vietnamese, name = English).
    """
    from io import BytesIO
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92)
    image_bytes = buf.getvalue()

    if bilingual:
        prompt = (
            "This is a numbered legend from a historical map of Saigon. Each row has: "
            "a Vietnamese name, a number, a grid-cell code (letter+number like 'H10'), "
            "and an English name. Extract EVERY numbered entry: n = the number, "
            "name_vn = Vietnamese name, name = English name, grid = the grid cell. "
            "Read the grid letter carefully — columns sit at ruled edges."
        )
    else:
        prompt = (
            "This is a numbered legend from a historical map. Each entry has a number, "
            "a name (French/Vietnamese, keep diacritics), and a grid-cell code "
            "(letter+number like 'C10'). Extract EVERY numbered entry: n, name, grid."
        )

    client, _ = _load_client()
    config = genai_types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        response_schema=_LEGEND_SCHEMA,
        max_output_tokens=65536,  # a 244-row bilingual legend is long — avoid truncation
    )
    resp = client.models.generate_content(
        model=model,
        contents=[genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
        config=config,
    )
    data = json.loads(resp.text)
    return data.get("entries", [])
