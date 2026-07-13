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


def test_missing_usage_is_distinct_from_zero_valued_usage():
    missing = normalize_billable_usage(None)
    present = normalize_billable_usage({'input_tokens': 0, 'output_tokens': 0})

    assert missing.usage_present is False
    assert present.usage_present is True
    assert missing.total_tokens == 0
    assert present.total_tokens == 0


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
