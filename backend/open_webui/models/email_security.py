from open_webui.internal.db import Base
from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, JSON, Text


class EmailChallenge(Base):
    __tablename__ = 'email_challenge'
    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False, index=True)
    purpose = Column(Text, nullable=False, index=True)
    code_hash = Column(Text, nullable=False)
    user_id = Column(Text, nullable=True, index=True)
    session_id = Column(Text, nullable=True)
    ip_address = Column(Text, nullable=True)
    expires_at = Column(BigInteger, nullable=False)
    resend_available_at = Column(BigInteger, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    consumed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    __table_args__ = (Index('email_challenge_lookup_idx', 'email', 'purpose', 'created_at'),)


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_token'
    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False, index=True)
    user_id = Column(Text, nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True, index=True)
    expires_at = Column(BigInteger, nullable=False)
    consumed_at = Column(BigInteger, nullable=True)
    ip_address = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class EmailTemplate(Base):
    __tablename__ = 'email_template'
    key = Column(Text, primary_key=True)
    subject = Column(Text, nullable=False)
    markdown_body = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(BigInteger, nullable=False)


class EmailDelivery(Base):
    __tablename__ = 'email_delivery'
    id = Column(Text, primary_key=True)
    template_key = Column(Text, nullable=False, index=True)
    recipient = Column(Text, nullable=False, index=True)
    subject = Column(Text, nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)
    status = Column(Text, nullable=False, index=True)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(BigInteger, nullable=True)
    sent_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)
