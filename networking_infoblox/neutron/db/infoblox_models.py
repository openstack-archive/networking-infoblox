# Copyright (c) 2015 Infoblox Inc.
# All Rights Reserved.
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

import sqlalchemy as sa

from neutron.db import model_base
from neutron.db import models_v2


class InfobloxGrid(model_base.BASEV2):
    """Multi-grid registration"""

    __tablename__ = 'infoblox_grids'

    grid_id = sa.Column(sa.Integer(), nullable=False, primary_key=True)
    grid_name = sa.Column(sa.String(128), nullable=True)
    grid_connection = sa.Column(sa.String(1024), nullable=False)
    __table_args__ = (
        sa.Index('ix_infoblox_grids_grid_name', 'grid_name'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "grid_id: %s, grid_name: %s, grid_connection: %s" % \
               (self.grid_id, self.grid_name, self.grid_connection)


class InfobloxGridMember(model_base.BASEV2):
    """Member registration per grid."""

    __tablename__ = 'infoblox_grid_members'

    member_id = sa.Column(sa.String(32), nullable=False, primary_key=True)
    grid_id = sa.Column(sa.Integer(),
                        sa.ForeignKey('infoblox_grids.grid_id',
                                      ondelete="CASCADE"),
                        nullable=False)
    member_name = sa.Column(sa.String(255), nullable=False)
    member_ip = sa.Column(sa.String(15), nullable=True)
    member_ipv6 = sa.Column(sa.String(64), nullable=True)
    member_type = sa.Column(sa.String(12), nullable=False)
    member_status = sa.Column(sa.String(16), nullable=False)
    __table_args__ = (
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
            'grid_id', 'member_status'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "member_id: %s, grid_id: %s, member_name: %s, member_ip: %s," \
               " member_ipv6: %s, member_type: %s, member_status: %s" % \
               (self.member_id, self.grid_id, self.member_name,
                self.member_ip, self.member_ipv6, self.member_type,
                self.member_status)


class InfobloxMapping(model_base.BASEV2, models_v2.HasId):
    """Network view mapping to Neutron objects."""

    __tablename__ = 'infoblox_mapping'

    network_view = sa.Column(sa.String(255), nullable=False)
    neutron_object_id = sa.Column(sa.String(255), nullable=False)
    neutron_object_name = sa.Column(sa.String(255), nullable=False)
    mapping_scope = sa.Column(sa.String(24), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint(
            'network_view', 'neutron_object_id', 'neutron_object_name',
            name='uniq_infoblox_mapping_network_view_neutron_object_id'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "network_view: %s, neutron_object_id: %s, " \
               "neutron_object_name: %s, mapping_scope: %s" % \
               (self.network_view, self.neutron_object_id,
                self.neutron_object_name, self.mapping_scope)


class InfobloxMappingMember(model_base.BASEV2, models_v2.HasId):
    """Network views assigned to infoblox members."""

    __tablename__ = 'infoblox_mapping_members'

    mapping_id = sa.Column(sa.String(36),
                           sa.ForeignKey('infoblox_mapping.id',
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    member_id = sa.Column(sa.String(32),
                          sa.ForeignKey('infoblox_grid_members.member_id',
                                        ondelete="CASCADE"),
                          nullable=False,
                          primary_key=True)
    mapping_relation = sa.Column(sa.String(24), nullable=False)

    def __repr__(self):
        return "mapping_id: %s, member_id: %s, mapping_relation: %s, " % \
               (self.mapping_id, self.member_id, self.mapping_relation)


class InfobloxServiceMember(model_base.BASEV2):
    """Member assignment per service."""

    __tablename__ = 'infoblox_service_members'

    member_id = sa.Column(sa.String(32),
                          sa.ForeignKey('infoblox_grid_members.member_id',
                                        ondelete="CASCADE"),
                          nullable=False,
                          primary_key=True)
    service = sa.Column(sa.String(12), nullable=False, primary_key=True)
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id',
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    __table_args__ = (
        sa.Index('ix_infoblox_service_members_network_id',
                 'network_id'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "member_id: %s, service: %s, network_id: %s" % \
               (self.member_id, self.service, self.network_id)


class InfobloxNetworkView(model_base.BASEV2):
    """Network views used in Neutron networks.

    This is needed to properly delete network views in NIOS on network
    delete.
    """

    __tablename__ = 'infoblox_network_views'

    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey("networks.id",
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    network_view = sa.Column(sa.String(255), nullable=False)


class InfobloxManagementNetwork(model_base.BASEV2):
    """Management network for DHCP relay interfaces.

    IP addresses are allocated for the management network for DHCP relay
    interface.
    """

    __tablename__ = 'infoblox_management_networks'

    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey("networks.id",
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    ip_address = sa.Column(sa.String(64), nullable=False, primary_key=True)
    ip_version = sa.Column(sa.Integer(), default=4, nullable=False)
    ip_address_ref = sa.Column(sa.String(255), nullable=False)


class InfobloxObject(model_base.BASEV2):
    """Infoblox object reference ids that are created by neutron."""

    __tablename__ = 'infoblox_objects'

    object_id = sa.Column(sa.String(255), nullable=False,
                          primary_key=True)
    object_type = sa.Column(sa.String(48), nullable=False)
    neutron_object_id = sa.Column(sa.String(length=255), nullable=False)
    search_hash = sa.Column(sa.Integer(), nullable=False)

    __table_args__ = (
        sa.Index(
            'ix_infoblox_objects_search_hash',
            'search_hash'),
        model_base.BASEV2.__table_args__
    )
