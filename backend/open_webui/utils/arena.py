from __future__ import annotations

import random

from fastapi import HTTPException, status


async def _check_model_access(user, model) -> None:
    from open_webui.utils.models import check_model_access

    await check_model_access(user, model)


async def resolve_arena_model(request, form_data: dict, user, metadata: dict, model: dict) -> tuple[dict, str | None]:
    if model.get('owned_by') != 'arena':
        return model, None

    configured_ids = model.get('info', {}).get('meta', {}).get('model_ids')
    filter_mode = model.get('info', {}).get('meta', {}).get('filter_mode')
    excluded_ids = set(configured_ids or []) if filter_mode == 'exclude' else set()
    included_ids = list(configured_ids or []) if filter_mode != 'exclude' else list(request.app.state.MODELS.keys())

    candidates = []
    seen = set()
    for model_id in included_ids:
        if not isinstance(model_id, str) or model_id in seen or model_id in excluded_ids:
            continue
        seen.add(model_id)
        candidate = request.app.state.MODELS.get(model_id)
        if not isinstance(candidate, dict) or candidate.get('owned_by') == 'arena':
            continue
        if getattr(user, 'role', None) == 'user':
            try:
                await _check_model_access(user, candidate)
            except Exception:
                continue
        candidates.append(candidate)

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No accessible models are available for this Arena.',
        )

    selected_model = random.choice(candidates)
    selected_model_id = selected_model.get('id')
    if not isinstance(selected_model_id, str) or not selected_model_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Arena selected an invalid model.',
        )
    form_data['model'] = selected_model_id
    metadata['selected_model_id'] = selected_model_id
    return selected_model, selected_model_id
