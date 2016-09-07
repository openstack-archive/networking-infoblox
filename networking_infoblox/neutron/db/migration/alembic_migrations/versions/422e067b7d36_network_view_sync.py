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

"""network_view_sync

Revision ID: 422e067b7d36
Revises: 256b90dd9824
Create Date: 2016-02-22 13:45:17.455133

"""

# revision identifiers, used by Alembic.
revision = '422e067b7d36'
down_revision = '256b90dd9824'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'infoblox_network_views',
        sa.Column('participated', sa.Boolean(), default=False,
                  nullable=False))

    op.add_column(
        'infoblox_network_views',
        sa.Column('default', sa.Boolean(), default=False,
                  nullable=False))
