import pytest

from open_webui.utils.email_security import is_registration_email_allowed, normalize_allowed_domains


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
