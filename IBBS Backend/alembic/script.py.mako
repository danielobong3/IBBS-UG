% for line in template_args['prelude']:
${line}
% endfor

"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | commacomma}
Create Date: ${create_date}
"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    pass


def downgrade():
    pass
