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
    grid_status = sa.Column(sa.String(length=6), nullable=False)
    gm_id = sa.Column(sa.String(32), nullable=False)
    __table_args__ = (
        sa.Index('ix_infoblox_grids_grid_name', 'grid_name'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return ("grid_id: %s, grid_name: %s, grid_connection: %s, "
                "grid_status: %s, gm_id: %s" % (self.grid_id, self.grid_name,
                                                self.grid_connection,
                                                self.grid_status, self.gm_id))


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
    member_dhcp_ip = sa.Column(sa.String(length=15), nullable=True)
    member_dhcp_ipv6 = sa.Column(sa.String(length=64), nullable=True)
    member_dns_ip = sa.Column(sa.String(length=15), nullable=True)
    member_dns_ipv6 = sa.Column(sa.String(length=64), nullable=True)
    member_wapi = sa.Column(sa.String(length=255), nullable=True)
    __table_args__ = (
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
        return ("member_id: %s, grid_id: %s, member_name: %s, "
                "member_wapi: %s, member_ip: %s, member_ipv6: %s, "
                "member_dhcp_ip: %s, member_dhcp_ipv6: %s, "
                "member_dns_ip: %s, member_dns_ipv6: %s, "
                "member_type: %s, member_status: %s" %
                (self.member_id, self.grid_id, self.member_name,
                 self.member_wapi, self.member_ip, self.member_ipv6,
                 self.member_dhcp_ip, self.member_dhcp_ipv6,
                 self.member_dns_ip, self.member_dns_ipv6,
                 self.member_type, self.member_status))


class InfobloxNetworkView(model_base.BASEV2):
    """Network views"""

    __tablename__ = 'infoblox_network_views'

    id = sa.Column(sa.String(length=36), nullable=False, primary_key=True)
    network_view = sa.Column(sa.String(255), nullable=False)
    grid_id = sa.Column(sa.Integer(), nullable=False)
    authority_member_id = sa.Column(sa.String(length=32), nullable=False)
    shared = sa.Column(sa.Boolean(), default=False, nullable=False)
    dns_view = sa.Column(sa.String(length=255), nullable=True)
    internal_network_view = sa.Column(sa.String(255), nullable=False)
    internal_dns_view = sa.Column(sa.String(length=255), nullable=True)
    participated = sa.Column(sa.Boolean(), default=False, nullable=False)
    default = sa.Column(sa.Boolean(), default=False, nullable=False)
    __table_args__ = (
        sa.UniqueConstraint(
            'network_view', 'grid_id',
            name='uniq_infoblox_network_views_network_view_grid_id'),
        sa.UniqueConstraint(
            'network_view', 'authority_member_id',
            name='uniq_infoblox_network_views_network_view_authority_member_id'
        ),
        sa.Index('ix_infoblox_network_views_grid_id_internal_network_view',
                 'grid_id', 'internal_network_view'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return ("id: %s, network_view: %s, grid_id: %s, "
                "authority_member_id: %s, shared: %s, dns_view: %s, "
                "internal_network_view:%s, internal_dns_view:%s,"
                "participated: %s, default: %s" %
                (self.id, self.network_view, self.grid_id,
                 self.authority_member_id, self.shared, self.dns_view,
                 self.internal_network_view, self.internal_dns_view,
                 self.participated, self.default))


class InfobloxNetworkViewMapping(model_base.BASEV2):
    """Network views that are mapping to Neutron networks.

    This is needed to properly delete network views in NIOS on network
    delete.
    """

    __tablename__ = 'infoblox_network_view_mapping'

    network_view_id = sa.Column(sa.String(36),
                                sa.ForeignKey("infoblox_network_views.id",
                                              ondelete="CASCADE"),
                                nullable=False,
                                primary_key=True)
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey("networks.id",
                                         ondelete="CASCADE"),
                           nullable=False,
                           primary_key=True)
    subnet_id = sa.Column(sa.String(36),
                          nullable=False,
                          primary_key=True)


class InfobloxMappingCondition(model_base.BASEV2):
    """Network view mapping conditions."""

    __tablename__ = 'infoblox_mapping_conditions'

    network_view_id = sa.Column(sa.String(36),
                                sa.ForeignKey('infoblox_network_views.id',
                                              ondelete="CASCADE"),
                                nullable=False,
                                primary_key=True)
    neutron_object_name = sa.Column(sa.String(48),
                                    nullable=False,
                                    primary_key=True)
    neutron_object_value = sa.Column(sa.String(255),
                                     nullable=False,
                                     primary_key=True)

    def __repr__(self):
        return ("network_view_id: %s, neutron_object_name: %s, "
                "neutron_object_value: %s" %
                (self.network_view_id, self.neutron_object_name,
                 self.neutron_object_value))


class InfobloxMappingMember(model_base.BASEV2):
    """Network views owned by infoblox members."""

    __tablename__ = 'infoblox_mapping_members'

    network_view_id = sa.Column(sa.String(36),
                                sa.ForeignKey('infoblox_network_views.id',
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
        return ("network_view_id: %s, member_id: %s, mapping_relation: %s, " %
                (self.network_view_id, self.member_id, self.mapping_relation))


class InfobloxServiceMember(model_base.BASEV2):
    """Member assignment per service."""

    __tablename__ = 'infoblox_service_members'

    network_view_id = sa.Column(sa.String(36),
                                sa.ForeignKey('infoblox_network_views.id',
                                              ondelete="CASCADE"),
                                nullable=False,
                                primary_key=True)
    member_id = sa.Column(sa.String(32),
                          sa.ForeignKey('infoblox_grid_members.member_id',
                                        ondelete="CASCADE"),
                          nullable=False,
                          primary_key=True)
    service = sa.Column(sa.String(12), nullable=False, primary_key=True)
    __table_args__ = (
        sa.UniqueConstraint(
            'member_id', 'service',
            name='uniq_infoblox_service_members_member_id_service'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return ("network_view_id: %s, member_id: %s, service: %s" %
                (self.network_view_id, self.member_id, self.service))


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


class InfobloxOperation(model_base.BASEV2, models_v2.HasId):
    """Operational data like last sync time."""
    __tablename__ = 'infoblox_operations'

    op_type = sa.Column(sa.String(48), nullable=False)
    op_value = sa.Column(sa.String(255), nullable=False)
    __table_args__ = (
        sa.UniqueConstraint(
            'op_type',
            name='uniq_infoblox_operations_op_type'),
        model_base.BASEV2.__table_args__
    )

    def __repr__(self):
        return "op_type: %s, op_value: %s" % (self.op_type, self.op_value)


class InfobloxTenant(model_base.BASEV2):
    """Tenant id to tenant name mapping."""
    __tablename__ = 'infoblox_tenants'

    tenant_id = sa.Column(sa.String(64),
                          nullable=False,
                          primary_key=True)
    tenant_name = sa.Column(sa.String(64), nullable=False)


class InfobloxInstance(model_base.BASEV2):
    """Tenant id to tenant name mapping."""
    __tablename__ = 'infoblox_instances'

    instance_id = sa.Column(sa.String(64),
                            nullable=False,
                            primary_key=True)
    instance_name = sa.Column(sa.String(255), nullable=False)


class InfobloxNetwork(model_base.BASEV2):
    """Network id to network name mapping."""
    __tablename__ = 'infoblox_networks'

    network_id = sa.Column(sa.String(64),
                           nullable=False,
                           primary_key=True)
    network_name = sa.Column(sa.String(255), nullable=False)
