from open_webui.models.email_security import EmailChallenge, EmailDelivery, EmailTemplate, PasswordResetToken


def test_email_security_tables_expose_required_columns():
    assert {
        'id', 'email', 'purpose', 'code_hash', 'user_id', 'session_id', 'ip_address',
        'expires_at', 'resend_available_at', 'attempts', 'max_attempts', 'consumed_at',
        'claimed_at', 'created_at'
    } <= set(EmailChallenge.__table__.columns.keys())
    assert {
        'id', 'email', 'user_id', 'token_hash', 'expires_at', 'consumed_at', 'ip_address', 'created_at'
    } <= set(PasswordResetToken.__table__.columns.keys())
    assert {'key', 'subject', 'markdown_body', 'is_enabled', 'updated_at'} <= set(
        EmailTemplate.__table__.columns.keys()
    )
    assert {
        'id', 'template_key', 'recipient', 'subject', 'status', 'error', 'attempts',
        'last_attempt_at', 'sent_at', 'created_at'
    } <= set(EmailDelivery.__table__.columns.keys())
