from pathlib import Path

from open_webui.models.auths import EmailCodeSigninForm, SignupForm


def test_auth_forms_and_routes_expose_verified_signup_and_email_login():
    assert 'verification_token' in SignupForm.model_fields
    assert set(EmailCodeSigninForm.model_fields) == {'email', 'verification_token'}

    source = (Path(__file__).resolve().parents[2] / 'routers' / 'auths.py').read_text(encoding='utf-8')
    assert "@router.post('/signin/email-code'" in source
    assert 'claim_email_verification_ticket(' in source
    assert 'email_verified_at=email_verified_at' in source
