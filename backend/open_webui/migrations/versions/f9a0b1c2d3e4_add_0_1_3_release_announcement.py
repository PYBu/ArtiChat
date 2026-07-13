"""Add the ArtiChat 0.1.3 release announcement.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f9a0b1c2d3e4'
down_revision: Union[str, None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANNOUNCEMENT_ID = 'ann_release_0_1_3'
ANNOUNCEMENT_TITLE = 'ArtiChat 0.1.3 已发布'
ANNOUNCEMENT_BODY = """ArtiChat 0.1.3 完成了一次覆盖管理、计费、账号安全与邮件体验的系统升级。

主要更新
• 新增注册域名限制、邮箱验证码登录、密码重置和登录邮箱变更。
• 新增 SMTP 设置、邮件模板、发送记录与品牌化 HTML 邮件。
• 优化订阅、模型权限、兑换码、礼品、公告和用量管理，并适配移动端。
• Token 计费细分为输入、输出、缓存创建与缓存读取，并增强用量审计。
• 平台名称、关于内容和浅色/深色 Logo 现在可由管理员配置。

管理员提示：启用邮件验证前请先完成 SMTP 配置；本次升级包含数据库迁移，建议升级前备份数据。"""
RELEASED_AT = 1_783_900_800


def _announcement_table() -> sa.TableClause:
    return sa.table(
        'announcement',
        sa.column('id', sa.Text()),
        sa.column('title', sa.Text()),
        sa.column('body', sa.Text()),
        sa.column('display_mode', sa.Text()),
        sa.column('button_label', sa.Text()),
        sa.column('icon', sa.Text()),
        sa.column('is_active', sa.Boolean()),
        sa.column('starts_at', sa.BigInteger()),
        sa.column('ends_at', sa.BigInteger()),
        sa.column('sort_order', sa.BigInteger()),
        sa.column('created_by', sa.Text()),
        sa.column('created_at', sa.BigInteger()),
        sa.column('updated_at', sa.BigInteger()),
    )


def upgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    announcement = _announcement_table()
    exists = conn.execute(
        sa.select(announcement.c.id).where(announcement.c.id == ANNOUNCEMENT_ID)
    ).scalar_one_or_none()
    if exists is not None:
        return

    conn.execute(
        announcement.insert().values(
            id=ANNOUNCEMENT_ID,
            title=ANNOUNCEMENT_TITLE,
            body=ANNOUNCEMENT_BODY,
            display_mode='once',
            button_label='开始使用',
            icon='0.1.3',
            is_active=True,
            starts_at=None,
            ends_at=None,
            sort_order=-100,
            created_by='system',
            created_at=RELEASED_AT,
            updated_at=RELEASED_AT,
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if 'announcement' not in sa.inspect(conn).get_table_names():
        return

    announcement = _announcement_table()
    conn.execute(announcement.delete().where(announcement.c.id == ANNOUNCEMENT_ID))
