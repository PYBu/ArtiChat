from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from fastapi.responses import JSONResponse, StreamingResponse
from open_webui.models.subscriptions import calculate_token_cost_micros, now_ts
from open_webui.utils.response import normalize_usage
from open_webui.utils.subscriptions import (
    ChatpointReservationConflictError,
    assert_chatpoint_available,
    assert_model_subscription_access,
    bill_model_usage,
    ensure_metered_stream_usage_options,
    ensure_subscription_current,
    extend_chatpoint_reservation,
    get_request_client_ip,
    release_chatpoint_reservation,
    renew_chatpoint_reservation,
    reserve_chatpoint_batch,
    reserve_chatpoints,
    resize_chatpoint_reservation_batch,
    stream_event_has_content,
)

INTERNAL_BILLING_MARKER = '_artichat_internal_billing'
HOSTED_POLICY_MODEL_ID = '_artichat_hosted_policy_model_id'
RESERVATION_ID = '_artichat_chatpoint_reservation_id'
RESERVATION_INPUT_TOKENS = '_artichat_reservation_input_tokens'
RESERVATION_OUTPUT_TOKENS = '_artichat_reservation_output_tokens'
RESERVATION_AMOUNT_MICROS = '_artichat_reservation_amount_micros'
RESERVATION_PREPARED_DISPATCH = '_artichat_reservation_prepared_dispatch'
RESERVATION_METADATA_KEYS = (
    RESERVATION_ID,
    RESERVATION_INPUT_TOKENS,
    RESERVATION_OUTPUT_TOKENS,
    RESERVATION_AMOUNT_MICROS,
    RESERVATION_PREPARED_DISPATCH,
)

DEFAULT_RESERVED_OUTPUT_TOKENS = 4096
MAX_RESERVED_OUTPUT_TOKENS = 65536
IMAGE_INPUT_TOKEN_BUDGET = 8192
RESERVATION_FIXED_INPUT_TOKENS = 1024
RESERVATION_LEASE_SECONDS = 30 * 60
RESERVATION_HEARTBEAT_SECONDS = 5 * 60

_reservation_heartbeat_tasks: dict[str, asyncio.Task] = {}

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HostedInferenceContext:
    request: Any
    user: Any
    model_id: str
    policy: dict[str, Any]
    metadata: dict[str, Any]
    started_at: float


@dataclass(frozen=True)
class HostedReservationQuote:
    input_tokens: int
    output_tokens: int
    amount_micros: int


def clear_hosted_inference_reservation_metadata(metadata: dict | None) -> None:
    if not isinstance(metadata, dict):
        return
    for key in RESERVATION_METADATA_KEYS:
        metadata.pop(key, None)


def _is_byok_model(request, model_id: str) -> bool:
    direct_model = getattr(request.state, 'model', None)
    return (
        getattr(request.state, 'direct', False) is True
        and isinstance(direct_model, dict)
        and direct_model.get('id') == model_id
    )


def _get_model(request, model_id: str) -> dict:
    model = request.app.state.MODELS.get(model_id)
    if model is None:
        raise ValueError('Model not found')
    return model


def _ensure_child_request_metadata(form_data: dict) -> dict[str, Any]:
    metadata = form_data.get('metadata')
    if not isinstance(metadata, dict):
        metadata = {}
        form_data['metadata'] = metadata

    if metadata.get(INTERNAL_BILLING_MARKER) is not True:
        # A derived task is a separate billable request. Never inherit the
        # parent completion's hold when request.state metadata is copied.
        clear_hosted_inference_reservation_metadata(metadata)
        parent_request_id = metadata.get('request_id')
        if parent_request_id:
            metadata['parent_request_id'] = parent_request_id
        metadata['request_id'] = str(uuid4())
        metadata[INTERNAL_BILLING_MARKER] = True
    elif not metadata.get('request_id'):
        metadata['request_id'] = str(uuid4())
    return metadata


def _estimate_value_tokens(value: Any, *, depth: int = 0) -> int:
    if depth > 16:
        return 256
    if value is None:
        return 1
    if isinstance(value, str):
        if value.lstrip().lower().startswith('data:image/'):
            return IMAGE_INPUT_TOKEN_BUDGET
        return max(len(value.encode('utf-8', 'replace')), 1)
    if isinstance(value, (bool, int, float)):
        return 16
    if isinstance(value, dict):
        return 4 + sum(
            _estimate_value_tokens(key, depth=depth + 1) + _estimate_value_tokens(item, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return 4 + sum(_estimate_value_tokens(item, depth=depth + 1) for item in value)
    return 256


def estimate_hosted_input_tokens(form_data: dict) -> int:
    provider_payload = {
        key: value
        for key, value in form_data.items()
        if key not in {'metadata', 'stream', 'stream_options'}
    }
    return RESERVATION_FIXED_INPUT_TOKENS + _estimate_value_tokens(provider_payload)


def _decimal_price(policy: dict, key: str) -> Decimal:
    try:
        value = Decimal(str(policy.get(key, '0') or '0'))
    except InvalidOperation as exc:
        raise ValueError(f'Invalid hosted inference price: {key}') from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f'Invalid hosted inference price: {key}')
    return value


def _requested_output_tokens(form_data: dict) -> tuple[int, tuple[str, ...]]:
    values: list[int] = []
    source_keys: list[str] = []
    for key in ('max_tokens', 'max_completion_tokens', 'max_output_tokens'):
        if key not in form_data or form_data[key] is None:
            continue
        try:
            value = int(form_data[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Invalid hosted inference output limit: {key}') from exc
        values.append(min(value, MAX_RESERVED_OUTPUT_TOKENS) if value > 0 else MAX_RESERVED_OUTPUT_TOKENS)
        source_keys.append(key)

    options = form_data.get('options')
    if isinstance(options, dict):
        for key in ('num_predict', 'max_tokens'):
            if key not in options or options[key] is None:
                continue
            try:
                value = int(options[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Invalid hosted inference output limit: options.{key}') from exc
            values.append(min(value, MAX_RESERVED_OUTPUT_TOKENS) if value > 0 else MAX_RESERVED_OUTPUT_TOKENS)
            source_keys.append(f'options.{key}')
    return (min(values), tuple(source_keys)) if values else (DEFAULT_RESERVED_OUTPUT_TOKENS, ())


def _apply_output_token_limit(form_data: dict, limit: int, source_keys: tuple[str, ...]) -> None:
    # max_tokens is the canonical cross-provider limit. Adapter-specific
    # aliases are also clamped so no later conversion can select a larger one.
    form_data['max_tokens'] = limit
    for source_key in source_keys:
        if source_key.startswith('options.'):
            form_data.setdefault('options', {})[source_key.removeprefix('options.')] = limit
        else:
            form_data[source_key] = limit


def _quote_hosted_chatpoints(
    form_data: dict,
    policy: dict,
    *,
    available_micros: int,
) -> HostedReservationQuote:
    return _quote_hosted_chatpoint_batch(
        [form_data],
        [policy],
        available_micros=available_micros,
    )[0]


def _quote_hosted_chatpoint_batch(
    form_data_items: list[dict],
    policies: list[dict],
    *,
    available_micros: int,
) -> list[HostedReservationQuote]:
    if len(form_data_items) != len(policies):
        raise ValueError('Hosted inference batch policy mismatch')
    if not form_data_items:
        return []

    candidates = []
    for form_data, policy in zip(form_data_items, policies):
        input_tokens = estimate_hosted_input_tokens(form_data)
        input_price = max(
            _decimal_price(policy, 'input_chatpoint_per_million'),
            _decimal_price(policy, 'cache_creation_chatpoint_per_million'),
            _decimal_price(policy, 'cache_read_chatpoint_per_million'),
        )
        output_price = _decimal_price(policy, 'output_chatpoint_per_million')
        input_cost_micros = calculate_token_cost_micros(
            input_tokens=input_tokens,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            input_chatpoint_per_million=input_price,
            output_chatpoint_per_million=output_price,
            cache_creation_chatpoint_per_million='0',
            cache_read_chatpoint_per_million='0',
        )
        requested_output_tokens, source_keys = _requested_output_tokens(form_data)
        desired_output_cost_micros = calculate_token_cost_micros(
            input_tokens=0,
            output_tokens=requested_output_tokens,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            input_chatpoint_per_million='0',
            output_chatpoint_per_million=output_price,
            cache_creation_chatpoint_per_million='0',
            cache_read_chatpoint_per_million='0',
        )
        candidates.append(
            {
                'form_data': form_data,
                'input_tokens': input_tokens,
                'input_price': input_price,
                'input_cost_micros': input_cost_micros,
                'output_price': output_price,
                'requested_output_tokens': requested_output_tokens,
                'source_keys': source_keys,
                'desired_output_cost_micros': desired_output_cost_micros,
                'allocated_output_micros': 0,
            }
        )

    total_input_micros = sum(item['input_cost_micros'] for item in candidates)
    if total_input_micros > available_micros:
        raise PermissionError('CHATPOINT_BALANCE_INSUFFICIENT_FOR_INPUT')

    remaining_micros = available_micros - total_input_micros
    paid_output = [item for item in candidates if item['output_price'] > 0]
    minimum_output_micros = {
        id(item): calculate_token_cost_micros(
            input_tokens=0,
            output_tokens=1,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            input_chatpoint_per_million='0',
            output_chatpoint_per_million=item['output_price'],
            cache_creation_chatpoint_per_million='0',
            cache_read_chatpoint_per_million='0',
        )
        for item in paid_output
    }
    minimum_total = sum(minimum_output_micros.values())
    if minimum_total > remaining_micros:
        raise PermissionError('CHATPOINT_BALANCE_INSUFFICIENT_FOR_OUTPUT')

    desired_total = sum(item['desired_output_cost_micros'] for item in paid_output)
    if desired_total <= remaining_micros:
        for item in paid_output:
            item['allocated_output_micros'] = item['desired_output_cost_micros']
    elif paid_output:
        for item in paid_output:
            item['allocated_output_micros'] = minimum_output_micros[id(item)]
        distributable = remaining_micros - minimum_total
        extra_needs = {
            id(item): item['desired_output_cost_micros'] - minimum_output_micros[id(item)]
            for item in paid_output
        }
        total_extra_need = sum(extra_needs.values())
        if distributable > 0 and total_extra_need > 0:
            distributed = 0
            for item in paid_output:
                share = min(
                    extra_needs[id(item)],
                    distributable * extra_needs[id(item)] // total_extra_need,
                )
                item['allocated_output_micros'] += share
                distributed += share
            leftover = distributable - distributed
            for item in paid_output:
                if leftover <= 0:
                    break
                remaining_need = item['desired_output_cost_micros'] - item['allocated_output_micros']
                extra = min(leftover, remaining_need)
                item['allocated_output_micros'] += extra
                leftover -= extra

    quotes = []
    for item in candidates:
        output_tokens = item['requested_output_tokens']
        if item['output_price'] > 0:
            output_tokens = min(
                output_tokens,
                int(
                    (
                        Decimal(item['allocated_output_micros']) / item['output_price']
                    ).to_integral_value(rounding=ROUND_FLOOR)
                ),
            )
            if output_tokens < 1:
                raise PermissionError('CHATPOINT_BALANCE_INSUFFICIENT_FOR_OUTPUT')
        _apply_output_token_limit(item['form_data'], output_tokens, item['source_keys'])
        amount_micros = calculate_token_cost_micros(
            input_tokens=item['input_tokens'],
            output_tokens=output_tokens,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            input_chatpoint_per_million=item['input_price'],
            output_chatpoint_per_million=item['output_price'],
            cache_creation_chatpoint_per_million='0',
            cache_read_chatpoint_per_million='0',
        )
        quotes.append(
            HostedReservationQuote(
                input_tokens=item['input_tokens'],
                output_tokens=output_tokens,
                amount_micros=amount_micros,
            )
        )

    if sum(quote.amount_micros for quote in quotes) > available_micros:
        raise PermissionError('CHATPOINT_BALANCE_INSUFFICIENT_FOR_BATCH')
    return quotes


async def _reservation_heartbeat(reservation_id: str) -> None:
    try:
        while True:
            await asyncio.sleep(RESERVATION_HEARTBEAT_SECONDS)
            try:
                await renew_chatpoint_reservation(
                    reservation_id,
                    expires_at=now_ts() + RESERVATION_LEASE_SECONDS,
                )
            except ChatpointReservationConflictError:
                return
            except Exception:
                log.exception('Hosted inference reservation heartbeat failed; retrying')
    except asyncio.CancelledError:
        raise
    finally:
        current = asyncio.current_task()
        if _reservation_heartbeat_tasks.get(reservation_id) is current:
            _reservation_heartbeat_tasks.pop(reservation_id, None)


def _start_reservation_heartbeat(reservation_id: str) -> None:
    existing = _reservation_heartbeat_tasks.get(reservation_id)
    if existing is None or existing.done():
        _reservation_heartbeat_tasks[reservation_id] = asyncio.create_task(
            _reservation_heartbeat(reservation_id)
        )


async def stop_hosted_inference_reservation_heartbeat(reservation_id: str | None) -> None:
    if not reservation_id:
        return
    task = _reservation_heartbeat_tasks.pop(reservation_id, None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _reserve_hosted_chatpoints(
    form_data: dict,
    metadata: dict,
    user,
    subscription,
    model_id: str,
    policy: dict,
) -> str | None:
    if getattr(user, 'role', None) == 'admin' or policy.get('quota_mode') != 'metered':
        if metadata.get(RESERVATION_ID):
            await release_hosted_inference_reservation(
                metadata,
                'hosted policy no longer requires a reservation',
            )
        else:
            clear_hosted_inference_reservation_metadata(metadata)
        return None

    existing_id = metadata.get(RESERVATION_ID)
    available_micros = max(subscription.plan_balance_micros, 0) + max(subscription.check_balance_micros, 0)
    quote = _quote_hosted_chatpoints(
        form_data,
        policy,
        available_micros=available_micros,
    )

    request_id = metadata.get('request_id')
    if not isinstance(request_id, str) or not request_id:
        raise ValueError('Hosted inference request ID is missing')

    expires_at = now_ts() + RESERVATION_LEASE_SECONDS
    if isinstance(existing_id, str) and existing_id:
        await extend_chatpoint_reservation(
            existing_id,
            user_id=user.id,
            request_id=request_id,
            model_id=model_id,
            amount_micros=quote.amount_micros,
            expires_at=expires_at,
            metadata={
                'input_tokens_estimate': quote.input_tokens,
                'output_tokens_reserved': quote.output_tokens,
            },
        )
        metadata[RESERVATION_INPUT_TOKENS] = int(metadata.get(RESERVATION_INPUT_TOKENS) or 0) + quote.input_tokens
        metadata[RESERVATION_OUTPUT_TOKENS] = int(metadata.get(RESERVATION_OUTPUT_TOKENS) or 0) + quote.output_tokens
        metadata[RESERVATION_AMOUNT_MICROS] = (
            int(metadata.get(RESERVATION_AMOUNT_MICROS) or 0) + quote.amount_micros
        )
        _start_reservation_heartbeat(existing_id)
        return existing_id

    if quote.amount_micros <= 0:
        return None
    grant = await reserve_chatpoints(
        user.id,
        request_id=request_id,
        model_id=model_id,
        amount_micros=quote.amount_micros,
        expires_at=expires_at,
        metadata={
            'task': metadata.get('task'),
            'input_tokens_estimate': quote.input_tokens,
            'output_tokens_reserved': quote.output_tokens,
            'provider_call_count': 1,
        },
    )
    if not grant.acquired:
        raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_ALREADY_ACTIVE')

    metadata[RESERVATION_ID] = grant.reservation.id
    metadata[RESERVATION_INPUT_TOKENS] = quote.input_tokens
    metadata[RESERVATION_OUTPUT_TOKENS] = quote.output_tokens
    metadata[RESERVATION_AMOUNT_MICROS] = quote.amount_micros
    _start_reservation_heartbeat(grant.reservation.id)
    return grant.reservation.id


async def release_hosted_inference_reservation(metadata: dict | None, reason: str) -> None:
    if not isinstance(metadata, dict):
        return
    reservation_id = metadata.get(RESERVATION_ID)
    if not isinstance(reservation_id, str) or not reservation_id:
        return
    try:
        await release_chatpoint_reservation(reservation_id, reason=reason)
    except ChatpointReservationConflictError:
        log.debug('Hosted inference reservation is already terminal: %s', reservation_id)
    except Exception:
        log.exception('Failed to release hosted inference reservation')
        return
    finally:
        await stop_hosted_inference_reservation_heartbeat(reservation_id)
    clear_hosted_inference_reservation_metadata(metadata)


async def release_hosted_inference_reservation_shielded(metadata: dict | None, reason: str) -> None:
    task = asyncio.create_task(release_hosted_inference_reservation(metadata, reason))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await task


async def prepare_hosted_inference_batch(
    request,
    form_data_items: list[dict],
    user,
) -> None:
    """Atomically reserve all metered fanout requests before any provider dispatch."""

    if not form_data_items:
        return

    subscription = await ensure_subscription_current(user.id)
    metered_items = []
    metered_policies = []
    for form_data in form_data_items:
        model_id = form_data.get('model')
        if not isinstance(model_id, str) or not model_id:
            raise ValueError('Model not found')

        metadata = form_data.get('metadata')
        if not isinstance(metadata, dict):
            metadata = {}
            form_data['metadata'] = metadata
        if not metadata.get('request_id'):
            metadata['request_id'] = str(uuid4())

        if _is_byok_model(request, model_id):
            metadata['billing_mode'] = 'byok'
            metadata.pop('subscription_policy', None)
            metadata.pop(HOSTED_POLICY_MODEL_ID, None)
            clear_hosted_inference_reservation_metadata(metadata)
            continue

        model = _get_model(request, model_id)
        policy = assert_model_subscription_access(
            model,
            tier=subscription.tier,
            is_admin=(getattr(user, 'role', None) == 'admin'),
        )
        await assert_chatpoint_available(
            user.id,
            quota_mode=policy.quota_mode,
            is_admin=(getattr(user, 'role', None) == 'admin'),
        )
        metadata.pop('billing_mode', None)
        metadata['subscription_policy'] = policy.model_dump()
        metadata[HOSTED_POLICY_MODEL_ID] = model_id
        ensure_metered_stream_usage_options(form_data, metadata)

        if getattr(user, 'role', None) == 'admin' or policy.quota_mode != 'metered':
            clear_hosted_inference_reservation_metadata(metadata)
            continue
        if metadata.get(RESERVATION_ID):
            raise ChatpointReservationConflictError('CHATPOINT_RESERVATION_ALREADY_ACTIVE')
        metered_items.append(form_data)
        metered_policies.append(policy.model_dump())

    if not metered_items:
        return

    available_micros = max(subscription.plan_balance_micros, 0) + max(subscription.check_balance_micros, 0)
    quotes = _quote_hosted_chatpoint_batch(
        metered_items,
        metered_policies,
        available_micros=available_micros,
    )
    expires_at = now_ts() + RESERVATION_LEASE_SECONDS
    grants = await reserve_chatpoint_batch(
        user.id,
        [
            {
                'request_id': form_data['metadata']['request_id'],
                'model_id': form_data['model'],
                'amount_micros': quote.amount_micros,
                'expires_at': expires_at,
                'metadata': {
                    'task': form_data['metadata'].get('task'),
                    'input_tokens_estimate': quote.input_tokens,
                    'output_tokens_reserved': quote.output_tokens,
                    'provider_call_count': 1,
                    'fanout_batch_size': len(metered_items),
                },
            }
            for form_data, quote in zip(metered_items, quotes)
        ],
    )

    for form_data, quote, grant in zip(metered_items, quotes, grants):
        metadata = form_data['metadata']
        metadata[RESERVATION_ID] = grant.reservation.id
        metadata[RESERVATION_INPUT_TOKENS] = quote.input_tokens
        metadata[RESERVATION_OUTPUT_TOKENS] = quote.output_tokens
        metadata[RESERVATION_AMOUNT_MICROS] = quote.amount_micros
        metadata[RESERVATION_PREPARED_DISPATCH] = True
        _start_reservation_heartbeat(grant.reservation.id)


async def reconcile_hosted_inference_batch(
    request,
    form_data_items: list[dict],
    user,
) -> None:
    """Atomically resize prepared fanout holds to the final provider payloads."""

    if not form_data_items:
        return
    subscription = await ensure_subscription_current(user.id)
    metered_items = []
    metered_policies = []
    held_micros = 0
    for form_data in form_data_items:
        model_id = form_data.get('model')
        metadata = form_data.get('metadata')
        if not isinstance(model_id, str) or not isinstance(metadata, dict):
            raise ValueError('Hosted inference reconciliation context is missing')
        if _is_byok_model(request, model_id):
            continue

        policy = assert_model_subscription_access(
            _get_model(request, model_id),
            tier=subscription.tier,
            is_admin=(getattr(user, 'role', None) == 'admin'),
        )
        metadata['subscription_policy'] = policy.model_dump()
        metadata[HOSTED_POLICY_MODEL_ID] = model_id
        ensure_metered_stream_usage_options(form_data, metadata)
        if getattr(user, 'role', None) == 'admin' or policy.quota_mode != 'metered':
            continue
        reservation_id = metadata.get(RESERVATION_ID)
        if not isinstance(reservation_id, str) or not reservation_id:
            raise ChatpointReservationConflictError('CHATPOINT_PREPARED_RESERVATION_INVALID')
        held_micros += max(int(metadata.get(RESERVATION_AMOUNT_MICROS) or 0), 0)
        metered_items.append(form_data)
        metered_policies.append(policy.model_dump())

    if not metered_items:
        return

    available_micros = (
        max(subscription.plan_balance_micros, 0)
        + max(subscription.check_balance_micros, 0)
        + held_micros
    )
    quotes = _quote_hosted_chatpoint_batch(
        metered_items,
        metered_policies,
        available_micros=available_micros,
    )
    expires_at = now_ts() + RESERVATION_LEASE_SECONDS
    await resize_chatpoint_reservation_batch(
        user.id,
        [
            {
                'reservation_id': form_data['metadata'][RESERVATION_ID],
                'request_id': form_data['metadata']['request_id'],
                'model_id': form_data['model'],
                'amount_micros': quote.amount_micros,
                'expires_at': expires_at,
                'metadata': {
                    'input_tokens_estimate': quote.input_tokens,
                    'output_tokens_reserved': quote.output_tokens,
                    'fanout_batch_size': len(metered_items),
                },
            }
            for form_data, quote in zip(metered_items, quotes)
        ],
    )
    for form_data, quote in zip(metered_items, quotes):
        metadata = form_data['metadata']
        metadata[RESERVATION_INPUT_TOKENS] = quote.input_tokens
        metadata[RESERVATION_OUTPUT_TOKENS] = quote.output_tokens
        metadata[RESERVATION_AMOUNT_MICROS] = quote.amount_micros
        metadata[RESERVATION_PREPARED_DISPATCH] = True


async def prepare_hosted_inference(
    request,
    form_data: dict,
    user,
    *,
    model: dict | None = None,
    new_child_request: bool,
) -> HostedInferenceContext | None:
    """Apply billing policy to the actual model immediately before dispatch."""

    model_id = form_data.get('model')
    if not isinstance(model_id, str) or not model_id:
        raise ValueError('Model not found')

    metadata = form_data.get('metadata')
    if not isinstance(metadata, dict):
        metadata = {}
        form_data['metadata'] = metadata

    if _is_byok_model(request, model_id):
        metadata['billing_mode'] = 'byok'
        metadata.pop('subscription_policy', None)
        metadata.pop(HOSTED_POLICY_MODEL_ID, None)
        clear_hosted_inference_reservation_metadata(metadata)
        return None

    model = model or _get_model(request, model_id)
    subscription = await ensure_subscription_current(user.id)
    policy = assert_model_subscription_access(
        model,
        tier=subscription.tier,
        is_admin=(getattr(user, 'role', None) == 'admin'),
    )
    await assert_chatpoint_available(
        user.id,
        quota_mode=policy.quota_mode,
        is_admin=(getattr(user, 'role', None) == 'admin'),
    )

    if new_child_request:
        metadata = _ensure_child_request_metadata(form_data)
    elif not metadata.get('request_id'):
        metadata['request_id'] = str(uuid4())

    metadata.pop('billing_mode', None)
    metadata['subscription_policy'] = policy.model_dump()
    metadata[HOSTED_POLICY_MODEL_ID] = model_id
    ensure_metered_stream_usage_options(form_data, metadata)
    prepared_dispatch = metadata.pop(RESERVATION_PREPARED_DISPATCH, False) is True
    if prepared_dispatch:
        reservation_id = metadata.get(RESERVATION_ID)
        if (
            getattr(user, 'role', None) == 'admin'
            or policy.quota_mode != 'metered'
            or not isinstance(reservation_id, str)
            or not reservation_id
        ):
            raise ChatpointReservationConflictError('CHATPOINT_PREPARED_RESERVATION_INVALID')
        _start_reservation_heartbeat(reservation_id)
    else:
        await _reserve_hosted_chatpoints(
            form_data,
            metadata,
            user,
            subscription,
            model_id,
            policy.model_dump(),
        )
    return HostedInferenceContext(
        request=request,
        user=user,
        model_id=model_id,
        policy=policy.model_dump(),
        metadata=metadata,
        started_at=time.perf_counter(),
    )


def _response_data(response) -> dict | None:
    if isinstance(response, list) and len(response) == 1:
        response = response[0]
    if isinstance(response, dict):
        return response
    if isinstance(response, JSONResponse) and isinstance(response.body, bytes):
        try:
            data = json.loads(response.body.decode('utf-8', 'replace'))
        except (UnicodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None
    return None


def _response_is_billable(data: dict | None) -> bool:
    if not isinstance(data, dict) or data.get('error') is not None:
        return False
    if data.get('status') in {'cancelled', 'failed'}:
        return False
    if isinstance(data.get('usage'), dict) and data['usage']:
        return True
    if data.get('status') == 'completed' or data.get('output'):
        return True
    choices = data.get('choices')
    return isinstance(choices, list) and bool(choices)


def _billing_metadata(context: HostedInferenceContext, completion_status: str, usage: dict | None) -> dict:
    source = context.metadata
    return {
        'request_id': source.get('request_id'),
        'parent_request_id': source.get('parent_request_id'),
        'chat_id': source.get('chat_id'),
        'message_id': source.get('message_id'),
        'task': source.get('task'),
        'billing_scope': 'internal_inference',
        'billing_completion_status': completion_status,
        'billing_usage_observed': bool(usage),
    }


def _resolved_context(context: HostedInferenceContext) -> HostedInferenceContext:
    """Use the child model policy selected by arena/provider routing."""

    metadata = context.metadata
    model_id = metadata.get(HOSTED_POLICY_MODEL_ID)
    policy = metadata.get('subscription_policy')
    if isinstance(model_id, str) and isinstance(policy, dict):
        return HostedInferenceContext(
            request=context.request,
            user=context.user,
            model_id=model_id,
            policy=policy,
            metadata=metadata,
            started_at=context.started_at,
        )
    return context


async def _bill_context(
    context: HostedInferenceContext,
    usage: dict | None,
    *,
    completion_status: str,
    first_content_at: float | None = None,
) -> None:
    total_duration_ms = max(int((time.perf_counter() - context.started_at) * 1000), 0)
    first_token_latency_ms = (
        max(int((first_content_at - context.started_at) * 1000), 0) if first_content_at is not None else None
    )
    reservation_id = context.metadata.get(RESERVATION_ID)
    try:
        await bill_model_usage(
            user_id=context.user.id,
            model_id=context.model_id,
            quota_mode=context.policy.get('quota_mode', 'metered'),
            usage_multiplier=context.policy.get('usage_multiplier', '1'),
            pricing=context.policy,
            usage=usage,
            metadata=_billing_metadata(context, completion_status, usage),
            is_admin=(getattr(context.user, 'role', None) == 'admin'),
            request_id=context.metadata.get('request_id'),
            client_ip=get_request_client_ip(context.request),
            first_token_latency_ms=first_token_latency_ms,
            total_duration_ms=total_duration_ms,
            reservation_id=reservation_id,
            allow_partial_reservation=True,
            charge_reserved_on_missing_usage=True,
        )
    finally:
        await stop_hosted_inference_reservation_heartbeat(reservation_id)
    clear_hosted_inference_reservation_metadata(context.metadata)


async def _bill_shielded(
    context: HostedInferenceContext,
    usage: dict | None,
    *,
    completion_status: str,
    first_content_at: float | None = None,
) -> None:
    task = asyncio.create_task(
        _bill_context(
            context,
            usage,
            completion_status=completion_status,
            first_content_at=first_content_at,
        )
    )
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except Exception:
            log.exception('Failed to audit cancelled hosted inference usage')
        raise
    except Exception:
        log.exception('Failed to record hosted inference usage')


def _stream_chunk_has_content(chunk: Any) -> bool:
    line = chunk.decode('utf-8', 'replace') if isinstance(chunk, bytes) else chunk
    if not isinstance(line, str):
        return False
    for raw_part in line.splitlines():
        part = raw_part.removeprefix('data:').strip()
        if not part or part == '[DONE]':
            continue
        try:
            data = json.loads(part)
        except json.JSONDecodeError:
            continue
        if stream_event_has_content(data):
            return True
    return False


def _wrap_streaming_response(response: StreamingResponse, context: HostedInferenceContext) -> StreamingResponse:
    async def iterator():
        assistant_message: dict[str, Any] = {}
        completed = False
        first_content_at = None
        try:
            async for chunk in response.body_iterator:
                if first_content_at is None and _stream_chunk_has_content(chunk):
                    first_content_at = time.perf_counter()
                from open_webui.utils.middleware import update_assistant_message_from_stream

                update_assistant_message_from_stream(assistant_message, chunk)
                yield chunk
            completed = True
        finally:
            await _bill_shielded(
                context,
                assistant_message.get('usage'),
                completion_status='completed' if completed else 'stream_interrupted',
                first_content_at=first_content_at,
            )

    headers = dict(response.headers)
    headers.pop('content-length', None)
    return StreamingResponse(
        iterator(),
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
        background=response.background,
    )


async def generate_billed_chat_completion(request, form_data: dict, user):
    """Generate one derived/internal completion with its own auditable bill."""

    started_at = time.perf_counter()
    metadata = _ensure_child_request_metadata(form_data)
    model_id = form_data.get('model')
    if _is_byok_model(request, model_id):
        metadata['billing_mode'] = 'byok'
        metadata.pop('subscription_policy', None)
        metadata.pop(HOSTED_POLICY_MODEL_ID, None)

    from open_webui.utils.chat import generate_chat_completion

    try:
        response = await generate_chat_completion(request, form_data=form_data, user=user)
    except asyncio.CancelledError:
        await release_hosted_inference_reservation_shielded(
            form_data.get('metadata'),
            'internal inference cancelled before response',
        )
        raise
    except Exception:
        await release_hosted_inference_reservation(
            form_data.get('metadata'),
            'internal inference failed before response',
        )
        raise
    if _is_byok_model(request, model_id):
        return response

    metadata = form_data.get('metadata')
    if not isinstance(metadata, dict):
        raise RuntimeError('Hosted inference billing context is missing')
    actual_model_id = metadata.get(HOSTED_POLICY_MODEL_ID)
    policy = metadata.get('subscription_policy')
    if not isinstance(actual_model_id, str) or not isinstance(policy, dict):
        raise RuntimeError('Hosted inference billing context is missing')
    context = HostedInferenceContext(
        request=request,
        user=user,
        model_id=actual_model_id,
        policy=policy,
        metadata=metadata,
        started_at=started_at,
    )
    if isinstance(response, StreamingResponse):
        if response.status_code >= 400:
            await release_hosted_inference_reservation(
                metadata,
                'internal inference returned an error response',
            )
            return response
        return _wrap_streaming_response(response, context)

    data = _response_data(response)
    if _response_is_billable(data):
        await _bill_context(
            context,
            normalize_usage(data.get('usage') or {}),
            completion_status='completed',
        )
    else:
        await release_hosted_inference_reservation(
            metadata,
            'internal inference returned a non-billable response',
        )
    return response
