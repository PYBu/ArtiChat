from pathlib import Path

from open_webui.models.auths import UpdatePasswordForm
from open_webui.routers.subscriptions import BillingAddressForm


def test_password_and_billing_forms_accept_sensitive_action_grants():
    assert 'verification_token' in UpdatePasswordForm.model_fields
    assert 'verification_token' in BillingAddressForm.model_fields

    root = Path(__file__).resolve().parents[2]
    auth_source = (root / 'routers' / 'auths.py').read_text(encoding='utf-8')
    subscription_source = (root / 'routers' / 'subscriptions.py').read_text(encoding='utf-8')
    assert "action='password'" in auth_source
    assert "action='billing_address'" in subscription_source
    assert "@router.post('/update/email'" in auth_source
    assert "action='email_new'" in auth_source
