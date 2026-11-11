"""Create secure users separately from the Module 9 SQL exercise tables."""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.schema.CreateSchema("calculator", if_not_exists=True))
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("username", name="uq_calculator_users_username"),
        sa.UniqueConstraint("email", name="uq_calculator_users_email"),
        schema="calculator",
    )


def downgrade():
    op.drop_table("users", schema="calculator")
    op.execute(sa.schema.DropSchema("calculator"))
