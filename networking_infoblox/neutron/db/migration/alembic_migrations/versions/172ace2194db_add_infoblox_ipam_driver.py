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
revision = '172ace2194db'
down_revision = 'start_networking_infoblox'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # infoblox grids
    op.create_table(
        'infoblox_grids',
        sa.Column('grid_id', sa.Integer(), nullable=False),
        sa.Column('grid_name', sa.String(length=128), nullable=True),
        sa.Column('grid_connection', sa.String(length=1024), nullable=False),
        sa.Column('grid_status', sa.String(length=6), nullable=False),
        sa.PrimaryKeyConstraint('grid_id')
    )

    # infoblox grid members
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

    # infoblox mapping
    op.create_table(
        'infoblox_mapping',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('network_view', sa.String(length=255), nullable=False),
        sa.Column('neutron_object_id', sa.String(length=255), nullable=False),
        sa.Column('neutron_object_name', sa.String(length=255), nullable=True),
        sa.Column('mapping_scope', sa.String(length=24), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'network_view', 'neutron_object_id', 'neutron_object_name',
            name='uniq_infoblox_mapping_network_view_neutron_object_id')
    )

    # infoblox mapping members
    op.create_table(
        'infoblox_mapping_members',
        sa.Column('mapping_id', sa.String(length=36), nullable=False),
        sa.Column('member_id', sa.String(length=32), nullable=False),
        sa.Column('mapping_relation', sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(['mapping_id'],
                                ['infoblox_mapping.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('mapping_id', 'member_id')
    )

    # infoblox service members
    op.create_table(
        'infoblox_service_members',
        sa.Column('member_id', sa.String(length=48), nullable=False),
        sa.Column('service', sa.String(length=12), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id', 'service', 'network_id'),
        sa.Index(
            'ix_infoblox_service_members_network_id',
            'network_id')
    )

    # infoblox network views
    op.create_table(
        'infoblox_network_views',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('network_view', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id')
    )

    # infoblox management networks
    op.create_table(
        'infoblox_management_networks',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('ip_version', sa.Integer(), default=4, nullable=False),
        sa.Column('ip_address_ref', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id', 'ip_address')
    )

    # infoblox_objects
    op.create_table(
        'infoblox_objects',
        sa.Column('object_id', sa.String(length=255), nullable=False),
        sa.Column('object_type', sa.String(length=48), nullable=False),
        sa.Column('neutron_object_id', sa.String(length=255), nullable=False),
        sa.Column('search_hash', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('object_id'),
        sa.Index(
            'ix_infoblox_objects_search_hash',
            'search_hash')
    )
