from fastapi import HTTPException, Request, status

RAW_PROVIDER_PREFIXES = ('/openai/', '/ollama/')


def assert_raw_embedding_access(user) -> None:
    """Restrict unpriced embedding APIs to administrators in ArtiChat 0.2.2."""
    if getattr(user, 'role', None) != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                'Raw embedding endpoints are restricted to administrators until '
                'a dedicated embedding billing policy is configured.'
            ),
        )


def assert_direct_connection_targets(
    model_id: str | None,
    model_item: dict,
    message_ids: list[dict],
) -> None:
    """Prevent a BYOK request from dispatching any hosted model."""

    direct_model_id = model_item.get('id')
    target_model_ids = [entry.get('model_id') or model_id for entry in message_ids]
    if (
        not isinstance(direct_model_id, str)
        or not direct_model_id
        or model_id != direct_model_id
        or len(target_model_ids) != 1
        or target_model_ids[0] != direct_model_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Direct Connections requests must target exactly their declared BYOK model.',
        )


def assert_raw_provider_generation_access(request: Request, user) -> None:
    """Keep unmetered provider proxies out of non-admin API traffic.

    The provider router functions are also called internally by the metered
    `/api` chat pipeline. The original ASGI path distinguishes those calls
    from requests made directly to `/openai/*` or `/ollama/*`.
    """

    path = str(request.scope.get('path') or request.url.path)
    is_raw_provider_request = any(path.startswith(prefix) for prefix in RAW_PROVIDER_PREFIXES)
    if is_raw_provider_request and getattr(user, 'role', None) != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                'Direct provider generation endpoints are restricted to administrators. '
                'Use /api/v1/chat/completions or /api/v1/messages.'
            ),
        )
