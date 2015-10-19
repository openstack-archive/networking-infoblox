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

"""add_infoblox_ipam_driver

Revision ID: 256b90dd9824
Revises: None
Create Date: 2015-09-10 13:43:13.135126

"""

# revision identifiers, used by Alembic.
revision = '256b90dd9824'
down_revision = '172ace2194db'

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.add_column(
        'infoblox_network_views',
        sa.Column('authority_member_id', sa.String(length=32), nullable=False)
    )
    op.create_foreign_key(
        None,
        'infoblox_network_views',
        'infoblox_grid_members',
        ['authority_member_id'],
        ['member_id']
    )
    op.create_unique_constraint(
        'uniq_infoblox_network_views_network_view_authority_member_id',
        'infoblox_network_views',
        ['network_view', 'authority_member_id']
    )

    op.create_table(
        'infoblox_network_view_mapping',
        sa.Column('network_view_id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('subnet_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subnet_id'],
                                ['subnets.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_view_id'],
                                ['infoblox_network_views.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_view_id', 'network_id', 'subnet_id')
    )

    op.create_table(
        'infoblox_operations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('op_type', sa.String(length=48), nullable=False),
        sa.Column('op_value', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'op_type',
            name='uniq_infoblox_operations_op_type')
    )
