from decimal import Decimal

from open_webui.models.subscriptions import (
    CHATPOINT_MICROS,
    calculate_cost_micros,
    chatpoint_to_micros,
    debit_balances,
    micros_to_chatpoint,
)


def test_chatpoint_conversion_uses_fixed_precision():
    assert CHATPOINT_MICROS == 1_000_000
    assert chatpoint_to_micros(Decimal('1')) == 1_000_000
    assert chatpoint_to_micros(Decimal('0.000001')) == 1
    assert micros_to_chatpoint(1_500_000) == Decimal('1.5')


def test_cost_uses_tokens_per_chatpoint_and_multiplier():
    assert calculate_cost_micros(total_tokens=10_000, usage_multiplier='1') == 1_000_000
    assert calculate_cost_micros(total_tokens=10_000, usage_multiplier='2.5') == 2_500_000
    assert calculate_cost_micros(total_tokens=1, usage_multiplier='1') == 100


def test_cost_rounds_up_to_avoid_underbilling():
    assert calculate_cost_micros(total_tokens=1, usage_multiplier='0.001') == 1


def test_negative_multiplier_is_rejected():
    try:
        calculate_cost_micros(total_tokens=10_000, usage_multiplier='-1')
    except ValueError as exc:
        assert 'usage_multiplier must be greater than or equal to 0' in str(exc)
    else:
        raise AssertionError('negative multiplier should fail')


def test_debit_uses_plan_before_check():
    result = debit_balances(plan_balance_micros=1_000_000, check_balance_micros=2_000_000, cost_micros=2_500_000)

    assert result.plan_cost_micros == 1_000_000
    assert result.check_cost_micros == 1_500_000
    assert result.plan_balance_after_micros == 0
    assert result.check_balance_after_micros == 500_000


def test_debit_can_make_check_balance_negative():
    result = debit_balances(plan_balance_micros=500_000, check_balance_micros=250_000, cost_micros=1_000_000)

    assert result.plan_cost_micros == 500_000
    assert result.check_cost_micros == 500_000
    assert result.plan_balance_after_micros == 0
    assert result.check_balance_after_micros == -250_000
