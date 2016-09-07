# Copyright 2016 Infoblox Inc
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""store_instances_names_in_db

Revision ID: 5267e17f370f
Revises: 4d0bb1d080f8
Create Date: 2016-06-17 20:55:22.736519

"""

# revision identifiers, used by Alembic.
revision = '5267e17f370f'
down_revision = '4d0bb1d080f8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'infoblox_instances',
        sa.Column('instance_id', sa.String(64),
                  nullable=False, primary_key=True),
        sa.Column('instance_name', sa.String(255), nullable=False),
    )
