# Copyright (c) 2015 Infoblox Inc.
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

"""add_dns_view_column_to_network_views

Revision ID: 256b90dd9824
Revises: 172ace2194db
Create Date: 2016-02-01 13:32:13.135126

"""

# revision identifiers, used by Alembic.
revision = '256b90dd9824'
down_revision = '172ace2194db'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'infoblox_network_views',
        sa.Column('dns_view', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'infoblox_network_views',
        sa.Column('internal_network_view', sa.String(length=255),
                  nullable=False)
    )
    op.add_column(
        'infoblox_network_views',
        sa.Column('internal_dns_view', sa.String(length=255), nullable=True)
    )
    op.create_index(
        op.f('ix_infoblox_network_views_grid_id_internal_network_view'),
        'infoblox_network_views',
        ['grid_id', 'internal_network_view'],
        unique=False)
