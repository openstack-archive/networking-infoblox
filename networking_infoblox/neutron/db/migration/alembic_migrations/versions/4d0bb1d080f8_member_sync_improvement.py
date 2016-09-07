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

"""member_sync_improvement

Revision ID: 4d0bb1d080f8
Revises: 422e067b7d36
Create Date: 2016-02-22 17:57:57.245145

"""

# revision identifiers, used by Alembic.
revision = '4d0bb1d080f8'
down_revision = '422e067b7d36'

from alembic import op
import sqlalchemy as sa
from sqlalchemy import update

from networking_infoblox.neutron.common import utils


# simple models for infoblox_grids and infoblox_grid_members with only the
# fields needed for the migration
infoblox_grids = sa.Table(
    'infoblox_grids',
    sa.MetaData(),
    sa.Column('grid_id', sa.Integer(), nullable=False),
    sa.Column('grid_status', sa.String(length=6), nullable=False),
    sa.Column('gm_id', sa.String(length=32), nullable=False,
              default=utils.get_hash()))

infoblox_grid_members = sa.Table(
    'infoblox_grid_members',
    sa.MetaData(),
    sa.Column('member_id', sa.String(length=32), nullable=False),
    sa.Column('grid_id', sa.Integer(), nullable=False),
    sa.Column('member_ip', sa.String(length=15), nullable=True),
    sa.Column('member_ipv6', sa.String(length=64), nullable=True),
    sa.Column('member_type', sa.String(length=6), nullable=False))


def upgrade():
    op.add_column(
        'infoblox_grids',
        sa.Column('gm_id', sa.String(length=32), nullable=False,
                  default=utils.get_hash()))

    op.drop_constraint(
        constraint_name='uniq_infoblox_grid_members_grid_id_member_name',
        table_name='infoblox_grid_members',
        type_='unique')

    op.add_column(
        'infoblox_grid_members',
        sa.Column('member_dhcp_ip', sa.String(length=15), nullable=True))
    op.add_column(
        'infoblox_grid_members',
        sa.Column('member_dhcp_ipv6', sa.String(length=64), nullable=True))
    op.add_column(
        'infoblox_grid_members',
        sa.Column('member_dns_ip', sa.String(length=15), nullable=True))
    op.add_column(
        'infoblox_grid_members',
        sa.Column('member_dns_ipv6', sa.String(length=64), nullable=True))
    op.add_column(
        'infoblox_grid_members',
        sa.Column('member_wapi', sa.String(length=255), nullable=True))

    update_gm_ids()


def update_gm_ids():
    session = sa.orm.Session(bind=op.get_bind())
    q = session.query(infoblox_grid_members).filter(
        infoblox_grid_members.c.member_type == 'GM')
    gm_rows = q.all()
    for gm_row in gm_rows:
        u = update(infoblox_grids, infoblox_grids.c.grid_id == gm_row.grid_id)
        session.execute(u, {'gm_id': gm_row.member_id})
    session.commit()
