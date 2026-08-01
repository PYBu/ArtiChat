from open_webui.utils.subscriptions import ensure_metered_stream_usage_options


def test_metered_streaming_requests_include_usage_from_provider():
    payload = {'stream': True}
    metadata = {'subscription_policy': {'quota_mode': 'metered'}}

    ensure_metered_stream_usage_options(payload, metadata)

    assert payload['stream_options'] == {'include_usage': True}


def test_metered_streaming_preserves_existing_stream_options():
    payload = {'stream': True, 'stream_options': {'other': 'value'}}
    metadata = {'subscription_policy': {'quota_mode': 'metered'}}

    ensure_metered_stream_usage_options(payload, metadata)

    assert payload['stream_options'] == {'other': 'value', 'include_usage': True}


def test_unlimited_or_non_streaming_requests_are_not_changed():
    unlimited_payload = {'stream': True}
    non_streaming_payload = {'stream': False}

    ensure_metered_stream_usage_options(
        unlimited_payload,
        {'subscription_policy': {'quota_mode': 'unlimited'}},
    )
    ensure_metered_stream_usage_options(
        non_streaming_payload,
        {'subscription_policy': {'quota_mode': 'metered'}},
    )

    assert 'stream_options' not in unlimited_payload
    assert 'stream_options' not in non_streaming_payload
