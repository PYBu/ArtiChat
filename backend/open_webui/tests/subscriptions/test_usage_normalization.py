from open_webui.utils.response import merge_usage
from open_webui.utils.subscriptions import normalize_billable_usage


def normalized_fields(usage: dict) -> dict:
    return normalize_billable_usage(usage).model_dump(exclude={'raw_usage', 'usage_present'})


def test_openai_cached_prompt_tokens_are_removed_from_normal_input():
    assert normalized_fields(
        {
            'prompt_tokens': 1000,
            'completion_tokens': 200,
            'prompt_tokens_details': {'cached_tokens': 400},
        }
    ) == {
        'input_tokens': 600,
        'output_tokens': 200,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 400,
        'total_tokens': 1200,
    }


def test_anthropic_cache_tokens_remain_separate_from_normal_input():
    assert normalized_fields(
        {
            'input_tokens': 600,
            'output_tokens': 200,
            'cache_creation_input_tokens': 300,
            'cache_read_input_tokens': 100,
        }
    ) == {
        'input_tokens': 600,
        'output_tokens': 200,
        'cache_creation_tokens': 300,
        'cache_read_tokens': 100,
        'total_tokens': 1200,
    }


def test_anthropic_cache_tokens_are_summed_across_model_calls():
    merged = merge_usage(
        {
            'input_tokens': 600,
            'output_tokens': 100,
            'cache_creation_input_tokens': 300,
            'cache_read_input_tokens': 100,
        },
        {
            'input_tokens': 400,
            'output_tokens': 50,
            'cache_creation_input_tokens': 200,
            'cache_read_input_tokens': 50,
        },
    )

    assert merged['input_tokens'] == 1000
    assert merged['output_tokens'] == 150
    assert merged['cache_creation_tokens'] == 500
    assert merged['cache_read_tokens'] == 150
    assert merged['cache_creation_input_tokens'] == 200
    assert merged['cache_read_input_tokens'] == 50


def test_responses_api_cached_input_is_removed_from_normal_input():
    assert normalized_fields(
        {
            'input_tokens': 900,
            'output_tokens': 100,
            'input_tokens_details': {'cached_tokens': 250},
        }
    ) == {
        'input_tokens': 650,
        'output_tokens': 100,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 250,
        'total_tokens': 1000,
    }


def test_ollama_usage_has_no_cache_charge():
    assert normalized_fields({'prompt_eval_count': 80, 'eval_count': 20}) == {
        'input_tokens': 80,
        'output_tokens': 20,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'total_tokens': 100,
    }


def test_zero_or_unknown_usage_is_treated_as_missing():
    missing = normalize_billable_usage(None)
    zero = normalize_billable_usage({'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0})
    unknown = normalize_billable_usage({'provider_latency_ms': 25})

    assert missing.usage_present is False
    assert zero.usage_present is False
    assert unknown.usage_present is False
    assert missing.total_tokens == 0
    assert zero.total_tokens == 0
    assert unknown.total_tokens == 0


def test_total_only_usage_preserves_total_without_guessing_a_token_category():
    normalized = normalize_billable_usage({'total_tokens': 321})

    assert normalized.usage_present is True
    assert normalized.input_tokens == 0
    assert normalized.output_tokens == 0
    assert normalized.cache_creation_tokens == 0
    assert normalized.cache_read_tokens == 0
    assert normalized.total_tokens == 321
    assert normalized.unclassified_tokens == 321


def test_reported_total_above_component_sum_preserves_unclassified_difference():
    normalized = normalize_billable_usage(
        {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 230}
    )

    assert normalized.input_tokens == 100
    assert normalized.output_tokens == 50
    assert normalized.total_tokens == 230
    assert normalized.unclassified_tokens == 80


def test_cached_subset_larger_than_input_clamps_normal_input_to_zero():
    normalized = normalize_billable_usage(
        {
            'prompt_tokens': 100,
            'completion_tokens': 10,
            'prompt_tokens_details': {'cached_tokens': 120},
        }
    )

    assert normalized.input_tokens == 0
    assert normalized.cache_read_tokens == 120
    assert normalized.total_tokens == 130
