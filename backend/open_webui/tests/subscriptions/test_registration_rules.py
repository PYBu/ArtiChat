import pytest

from open_webui.utils.email_security import (
    generate_email_code,
    generate_reset_token,
    hash_email_secret,
    is_registration_email_allowed,
    normalize_allowed_domains,
    verify_email_secret,
)


def test_domain_allowlist_normalizes_case_whitespace_and_duplicates():
    assert normalize_allowed_domains([' Example.COM ', 'example.com', 'Team.Example.com']) == [
        'example.com',
        'team.example.com',
    ]
    assert normalize_allowed_domains('example.com, TEAM.example.com\nexample.com') == [
        'example.com',
        'team.example.com',
    ]


def test_empty_allowlist_accepts_any_valid_email():
    assert is_registration_email_allowed('user@anywhere.example', [], allow_subdomains=False) is True


def test_exact_domain_and_optional_subdomains():
    domains = ['example.com']
    assert is_registration_email_allowed('user@example.com', domains, allow_subdomains=False) is True
    assert is_registration_email_allowed('user@team.example.com', domains, allow_subdomains=False) is False
    assert is_registration_email_allowed('user@team.example.com', domains, allow_subdomains=True) is True
    assert is_registration_email_allowed('user@notexample.com', domains, allow_subdomains=True) is False


@pytest.mark.parametrize('email', ['', 'missing-at', '@example.com', 'user@', 'user@@example.com'])
def test_invalid_email_is_rejected_even_when_allowlist_is_empty(email):
    assert is_registration_email_allowed(email, [], allow_subdomains=True) is False


def test_invalid_allowlist_domains_are_ignored():
    assert normalize_allowed_domains(['', '@example.com', 'bad domain', '.example.com', 'example.com']) == [
        'example.com'
    ]


def test_email_codes_are_six_digits_and_hashes_are_purpose_bound():
    code = generate_email_code()
    assert len(code) == 6
    assert code.isdigit()

    digest = hash_email_secret(code, purpose='login', secret_key='test-secret')
    assert verify_email_secret(code, digest, purpose='login', secret_key='test-secret') is True
    assert verify_email_secret(code, digest, purpose='register', secret_key='test-secret') is False
    assert verify_email_secret('000000', digest, purpose='login', secret_key='test-secret') is False


def test_reset_tokens_are_high_entropy_and_hash_verifiable():
    first = generate_reset_token()
    second = generate_reset_token()
    assert first != second
    assert len(first) >= 40
    digest = hash_email_secret(first, purpose='password_reset', secret_key='test-secret')
    assert verify_email_secret(first, digest, purpose='password_reset', secret_key='test-secret') is True
