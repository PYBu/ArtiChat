import ast
from pathlib import Path

import pytest
from fastapi import HTTPException
from open_webui.utils.inference_access import assert_direct_connection_targets


def test_direct_connection_targets_only_its_declared_model():
    model_item = {'id': 'byok-model', 'direct': True}
    assert_direct_connection_targets(
        'byok-model',
        model_item,
        [{'model_id': 'byok-model', 'message_id': 'assistant-1'}],
    )


@pytest.mark.parametrize(
    ('model_id', 'message_ids'),
    [
        ('hosted-premium', [{'model_id': 'hosted-premium'}]),
        ('byok-model', [{'model_id': 'hosted-premium'}]),
        ('byok-model', [{'model_id': 'byok-model'}, {'model_id': 'hosted-premium'}]),
        ('byok-model', [{'model_id': 'byok-model'}, {'model_id': 'byok-model'}]),
    ],
)
def test_direct_connection_rejects_hosted_or_multi_model_targets(model_id, message_ids):
    with pytest.raises(HTTPException) as exc_info:
        assert_direct_connection_targets(model_id, {'id': 'byok-model', 'direct': True}, message_ids)

    assert exc_info.value.status_code == 400


def test_direct_connections_are_server_gated_and_excluded_from_hosted_billing():
    source = (Path(__file__).resolve().parents[2] / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(
        node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == 'chat_completion'
    )
    function_source = ast.get_source_segment(source, function)

    assert "Config.get('direct.enable')" in function_source
    assert "metadata['billing_mode'] = 'byok'" in function_source
    assert 'assert_direct_connection_targets(model_id, model_item, message_ids)' in function_source
    assert 'len(message_ids) > 8' in function_source
    assert 'A chat request may target at most 8 models.' in function_source
    assert "metadata = form_data['metadata']" in function_source
    assert 'release_hosted_inference_reservation' in function_source
    assert 'release_hosted_inference_reservation_shielded' in function_source

    billing_branch = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == 'is_direct_connection'
        and "metadata['billing_mode'] = 'byok'" in ast.get_source_segment(source, node)
    )
    direct_source = '\n'.join(ast.get_source_segment(source, node) or '' for node in billing_branch.body)
    hosted_source = '\n'.join(ast.get_source_segment(source, node) or '' for node in billing_branch.orelse)

    assert 'ensure_subscription_current' not in direct_source
    assert 'assert_chatpoint_available' not in direct_source
    assert 'ensure_subscription_current' in hosted_source
    assert 'assert_chatpoint_available' in hosted_source
