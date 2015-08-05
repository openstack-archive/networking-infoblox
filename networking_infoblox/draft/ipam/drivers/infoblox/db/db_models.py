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


class InfobloxGrid(model_base.BASEV2):
    """Registers Infoblox grids
    """
    __tablename__ = 'infoblox_grids'

    grid_id = sa.Column(sa.String(48), nullable=False, primary_key=True)
    grid_name = sa.Column(sa.String(128), nullable=False)
    grid_connection = sa.Column(sa.String(1024), nullable=False)
    __table_args__ = (
        sa.Index('ix_infoblox_grids_grid_name', 'grid_name'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "grid_id: %s, grid_name: %s, grid_connection: %s" % \
               (self.grid_id, self.grid_name, self.grid_connection)


class InfobloxGridMember(model_base.BASEV2):
    """Registers members for the grids.
    """
    __tablename__ = 'infoblox_grid_members'

    member_id = sa.Column(sa.String(48), nullable=False, primary_key=True)
    grid_id = sa.Column(sa.String(48),
                        sa.ForeignKey('infoblox_grids.grid_id',
                                      ondelete="CASCADE"),
                        nullable=False)
    member_name = sa.Column(sa.String(128), nullable=False)
    member_ip = sa.Column(sa.String(15), nullable=True)
    member_ipv6 = sa.Column(sa.String(64), nullable=True)
    member_type = sa.Column(sa.String(12), nullable=False)
    member_status = sa.Column(sa.String(10), nullable=False)
    __table_args__ = (
        sa.Index('ix_infoblox_grid_members_grid_id_member_name',
                 'grid_id', 'member_name'),
        sa.Index('ix_infoblox_grid_members_member_id_grid_id_member_ip',
                 'member_id', 'grid_id', 'member_ip'),
        sa.Index('ix_infoblox_grid_members_member_id_grid_id_member_ipv6',
                 'member_id', 'grid_id', 'member_ipv6'),
        sa.Index('ix_infoblox_grid_members_grid_id_member_status',
                 'grid_id', 'member_status'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "member_id: %s, grid_id: %s, member_name: %s, member_ip: %s," \
               " member_ipv6: %s, member_type: %s, member_status: %s" % \
               (self.member_id, self.grid_id, self.member_name,
                self.member_ip, self.member_ipv6, self.member_type,
                self.member_status)


class InfobloxMemberMapping(model_base.BASEV2):
    __tablename__ = 'infoblox_member_mapping'

    member_id = sa.Column(sa.String(48),
                          sa.ForeignKey('infoblox_grid_members.member_id',
                                        ondelete="CASCADE"),
                          nullable=False,
                          primary_key=True)
    mapping_id = sa.Column(sa.String(255), nullable=False, primary_key=True)
    mapping_scope = sa.Column(sa.String(24), nullable=False)
    mapping_relation = sa.Column(sa.String(24), nullable=False)

    def __repr__(self):
        return "member_id: %s, mapping_id: %s, mapping_scope: %s, " \
               "mapping_relation: %s" % (self.member_id, self.mapping_id,
                                         self.mapping_scope,
                                         self.mapping_relation)


class InfobloxMemberService(model_base.BASEV2):
    __tablename__ = 'infoblox_member_services'

    member_id = sa.Column(sa.String(48),
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
        sa.Index('ix_infoblox_member_services_network_id',
                 'network_id'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "member_id: %s, service: %s, network_id: %s" % \
               (self.member_id, self.service, self.network_id)


class InfobloxNetworkView(model_base.BASEV2):
    """Connects Infoblox network views with Openstack networks.

    This is needed to properly delete network views in NIOS on network
    delete
    """
    __tablename__ = 'infoblox_network_views'

    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey("networks.id",
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    network_view = sa.Column(sa.String(255), nullable=False)


class InfobloxManagementNetwork(model_base.BASEV2):
    """Holds IP addresses allocated on management network for DHCP relay
    interface
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


class InfobloxObjectMapping(model_base.BASEV2):
    """Holds Infoblox object reference ids that are created by neutron
    """
    __tablename__ = 'infoblox_object_mapping'

    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id',
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    subnet_id = sa.Column(sa.String(36),
                          sa.ForeignKey('subnets.id',
                                        ondelete="CASCADE"),
                          nullable=False,
                          primary_key=True)
    object_id = sa.Column(sa.String(255), nullable=False,
                          primary_key=True)
    port_id = sa.Column(sa.String(36),
                        sa.ForeignKey('ports.id',
                                      ondelete="CASCADE"),
                        nullable=True)
    object_type = sa.Column(sa.String(48), nullable=False)
    object_hash = sa.Column(sa.Integer(), nullable=False)
    __table_args__ = (
        sa.Index(
            'ix_infoblox_object_mapping_network_id_subnet_id_object_id',
            'network_id', 'subnet_id', 'object_id'),
        sa.Index(
            'ix_infoblox_object_mapping_network_id_subnet_id_object_hash',
            'network_id', 'subnet_id', 'object_hash'),
        model_base.BASEV2.__table_args__
    )
