# Copyright 2015 OpenStack Foundation
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

"""infoblox_ipam_driver

Revision ID: 78d27e9172
Revises: 45284803ad19
Create Date: 2015-06-04 15:57:34.815843

"""

# revision identifiers, used by Alembic.
revision = '172ace2194db'
down_revision = '599c6a226151'

from alembic import op
import sqlalchemy as sa


def upgrade(active_plugins=None, options=None):
    # infoblox grids
    op.create_table(
        'infoblox_grids',
        sa.Column('grid_id', sa.String(length=48), nullable=False),
        sa.Column('grid_name', sa.String(length=128), nullable=False),
        sa.Column('grid_connection', sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint('grid_id'))

    op.create_index(
        op.f('ix_infoblox_grids_grid_name'),
        'infoblox_grids',
        ['grid_name'],
        unique=True)

    # infoblox grid members
    op.create_table(
        'infoblox_grid_members',
        sa.Column('member_id', sa.String(length=48), nullable=False),
        sa.Column('grid_id', sa.String(length=48), nullable=False),
        sa.Column('member_name', sa.String(length=128), nullable=False),
        sa.Column('member_ip', sa.String(length=15), nullable=True),
        sa.Column('member_ipv6', sa.String(length=64), nullable=True),
        sa.Column('member_type', sa.String(length=12), nullable=False),
        sa.Column('member_status', sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(['grid_id'],
                                ['infoblox_grids.grid_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id'))

    op.create_index(
        op.f('ix_infoblox_grid_members_grid_id_member_name'),
        'infoblox_grid_members',
        ['grid_id', 'member_name'],
        unique=True)

    op.create_index(
        op.f('ix_infoblox_grid_members_member_id_grid_id_member_ip'),
        'infoblox_grid_members',
        ['member_id', 'grid_id', 'member_ip'],
        unique=True)

    op.create_index(
        op.f('ix_infoblox_grid_members_member_id_grid_id_member_ipv6'),
        'infoblox_grid_members',
        ['member_id', 'grid_id', 'member_ipv6'],
        unique=True)

    op.create_index(
        op.f('ix_infoblox_grid_members_grid_id_member_status'),
        'infoblox_grid_members',
        ['grid_id', 'member_status'],
        unique=False)

    # infoblox member mapping
    op.create_table(
        'infoblox_member_mapping',
        sa.Column('member_id', sa.String(length=48), nullable=False),
        sa.Column('mapping_id', sa.String(length=255), nullable=False),
        sa.Column('mapping_scope', sa.String(length=24), nullable=False),
        sa.Column('mapping_relation', sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id', 'mapping_id'))

    # infoblox service members
    op.create_table(
        'infoblox_member_services',
        sa.Column('member_id', sa.String(length=48), nullable=False),
        sa.Column('service', sa.String(length=12), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['member_id'],
                                ['infoblox_grid_members.member_id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id', 'service', 'network_id'))

    op.create_index(
        op.f('ix_infoblox_member_services_network_id'),
        'infoblox_member_services',
        ['network_id'],
        unique=False)

    # infoblox network views
    op.create_table(
        'infoblox_network_views',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('network_view', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id'))

    # infoblox management network ip allocations
    op.create_table(
        'infoblox_management_networks',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('ip_version', sa.Integer, default=4, nullable=False),
        sa.Column('ip_address_ref', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id', 'ip_address'))

    # infoblox_object_mapping
    op.create_table(
        'infoblox_object_mapping',
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.Column('subnet_id', sa.String(length=36), nullable=False),
        sa.Column('infoblox_id', sa.String(length=255), nullable=False),
        sa.Column('port_id', sa.String(length=36), nullable=True),
        sa.Column('obj_type', sa.String(length=48), nullable=False),
        sa.Column('obj_hash', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subnet_id'],
                                ['subnets.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['port_id'],
                                ['ports.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('network_id',
                                'subnet_id',
                                'infoblox_id'))

    op.create_index(
        op.f('ix_infoblox_object_mapping_network_id_subnet_id_infoblox_id'),
        'infoblox_object_mapping',
        ['network_id', 'subnet_id', 'infoblox_id'],
        unique=True)

    op.create_index(
        op.f('ix_infoblox_object_mapping_network_id_subnet_id_obj_hash'),
        'infoblox_object_mapping',
        ['network_id', 'subnet_id', 'obj_hash'],
        unique=True)
