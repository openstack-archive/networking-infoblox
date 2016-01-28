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

Revision ID: 172ace2194db
Revises: None
Create Date: 2015-09-10 13:43:13.135126

"""

# revision identifiers, used by Alembic.
revision = '172ace2194db'
down_revision = 'start_networking_infoblox'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'infoblox_grids',
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('grid_name', sa.String(length=128), nullable=True),
        sa.Column('grid_connection', sa.String(length=1024), nullable=False),
        sa.Column('grid_status', sa.String(length=6), nullable=False),
        sa.PrimaryKeyConstraint('grid_id')
    )

    op.create_table(
        'infoblox_grid_members',
        sa.Column('member_id', sa.String(length=32), nullable=False),
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('member_name', sa.String(length=255), nullable=False),
        sa.Column('member_ip', sa.String(length=15), nullable=True),
        sa.Column('member_ipv6', sa.String(length=64), nullable=True),
        sa.Column('member_type', sa.String(length=12), nullable=False),
        sa.Column('member_status', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['grid_id'],
                                ['infoblox_grids.grid_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id'),
        sa.UniqueConstraint(
            'grid_id', 'member_name',
            name='uniq_infoblox_grid_members_grid_id_member_name'),
        sa.UniqueConstraint(
            'member_id', 'grid_id', 'member_ip',
            name='uniq_infoblox_grid_members_member_id_grid_id_member_ip'),
        sa.UniqueConstraint(
            'member_id', 'grid_id', 'member_ipv6',
            name='uniq_infoblox_grid_members_member_id_grid_id_member_ipv6'),
        sa.Index(
            'ix_infoblox_grid_members_grid_id_member_status',
            'grid_id', 'member_status')
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

    op.create_table(
        'infoblox_network_views',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_view', sa.String(length=255), nullable=False),
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('authority_member_id', sa.String(length=32), nullable=False),
        sa.Column('shared', sa.Boolean(), default=False, nullable=False),
        sa.ForeignKeyConstraint(['authority_member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'network_view', 'grid_id',
            name='uniq_infoblox_network_views_network_view_grid_id'),
        sa.UniqueConstraint(
            'network_view', 'authority_member_id',
            name='uniq_infoblox_network_views_network_view_authority_member_id'
        )
    )

    op.create_table(
        'infoblox_network_view_mapping',
        sa.Column('network_view_id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('subnet_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_view_id'],
                                ['infoblox_network_views.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_view_id', 'network_id', 'subnet_id')
    )

    op.create_table(
        'infoblox_mapping_conditions',
        sa.Column('network_view_id', sa.String(length=36), nullable=False),
        sa.Column('neutron_object_name', sa.String(length=48), nullable=False),
        sa.Column('neutron_object_value', sa.String(length=255),
                  nullable=False),
        sa.ForeignKeyConstraint(['network_view_id'],
                                ['infoblox_network_views.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_view_id', 'neutron_object_name',
                                'neutron_object_value')
    )

    op.create_table(
        'infoblox_mapping_members',
        sa.Column('network_view_id', sa.String(length=36), nullable=False),
        sa.Column('member_id', sa.String(length=32), nullable=False),
        sa.Column('mapping_relation', sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(['network_view_id'],
                                ['infoblox_network_views.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_view_id', 'member_id')
    )

    op.create_table(
        'infoblox_service_members',
        sa.Column('network_view_id', sa.String(length=36), nullable=False),
        sa.Column('member_id', sa.String(length=48), nullable=False),
        sa.Column('service', sa.String(length=12), nullable=False),
        sa.ForeignKeyConstraint(['network_view_id'],
                                ['infoblox_network_views.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_view_id', 'member_id', 'service'),
        sa.UniqueConstraint(
            'member_id', 'service',
            name='uniq_infoblox_service_members_member_id_service')
    )

    op.create_table(
        'infoblox_tenants',
        sa.Column('tenant_id', sa.String(64),
                  nullable=False, primary_key=True),
        sa.Column('tenant_name', sa.String(64), nullable=False),
    )
