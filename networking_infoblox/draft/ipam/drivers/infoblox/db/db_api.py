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

from oslo_log import log as logging

from neutron.db import api as db_api
from neutron.db import external_net_db
from neutron.db import l3_db
from neutron.db import models_v2
from neutron.ipam.drivers.infoblox.common import constants as ib_const
from neutron.ipam.drivers.infoblox.db import db_models as ib_models


LOG = logging.getLogger(__name__)


# Grid Management
##############################################################################
def get_grids(session, grid_id=None, grid_name=None):
    """Returns grids."""
    q = session.query(ib_models.InfobloxGrid)
    if grid_id:
        q = q.filter(ib_models.InfobloxGrid.grid_id == grid_id)
    if grid_name:
        q = q.filter(ib_models.InfobloxGrid.grid_name == grid_name)
    return q.all()


def add_grid(session, grid_id, grid_name, grid_connection):
    grid = ib_models.InfobloxGrid(grid_id=grid_id,
                                  grid_name=grid_name,
                                  grid_connection=grid_connection)
    session.add(grid)
    return grid


def update_grid(session, grid_id, grid_name, grid_connection):
    session.query(ib_models.InfobloxGrid).\
        filter_by(grid_id=grid_id).\
        update({'grid_name': grid_name,
                'grid_connection': grid_connection})


def remove_grids(session, grid_ids):
    if grid_ids and isinstance(grid_ids, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxGrid)
            q = q.filter(ib_models.InfobloxGrid.grid_id.in_(grid_ids))
            q.delete()


#  Grid Members
##############################################################################
def get_members(session, member_id=None, grid_id=None, member_name=None,
                member_type=None, member_status=None):
    """Returns registered grid members."""
    q = session.query(ib_models.InfobloxGridMember)
    if member_id:
        q = q.filter(ib_models.InfobloxGridMember.member_id == member_id)
    if grid_id:
        q = q.filter(ib_models.InfobloxGridMember.grid_id == grid_id)
    if member_name:
        q = q.filter(ib_models.InfobloxGridMember.member_name == member_name)
    if member_type:
        q = q.filter(ib_models.InfobloxGridMember.member_type == member_type)
    if member_status:
        q = q.filter(ib_models.InfobloxGridMember.member_status ==
                     member_status)
    return q.all()


def get_members_in_service(session, network_id):
    sub_qry = session.query(ib_models.InfobloxMemberService.member_id)
    sub_qry = sub_qry.filter_by(network_id == network_id)
    q = session.query(ib_models.InfobloxGridMember)
    q = q.filter(ib_models.InfobloxMemberMapping.member_id.in_(sub_qry))
    return q.distinct()


def search_members(session, member_ids=None, member_names=None,
                   member_types=None, member_statuses=None):
    """Returns registered members."""
    q = session.query(ib_models.InfobloxGridMember)
    if member_ids and isinstance(member_ids, list):
        q = q.filter(ib_models.InfobloxGridMember.member_id.in_(member_ids))
    if member_names and isinstance(member_names, list):
        q = q.filter(ib_models.InfobloxGridMember.member_name.
                     in_(member_names))
    if member_types and isinstance(member_types, list):
        q = q.filter(ib_models.InfobloxGridMember.member_type.
                     in_(member_types))
    if member_statuses and isinstance(member_statuses, list):
        q = q.filter(ib_models.InfobloxGridMember.member_status.
                     in_(member_statuses))
    return q.all()


def add_member(session, member_id, grid_id, member_name, member_ip,
               member_ipv6, member_type, member_status):

    member = ib_models.InfobloxGridMember(member_id=member_id,
                                          grid_id=grid_id,
                                          member_name=member_name,
                                          member_ip=member_ip,
                                          member_ipv6=member_ipv6,
                                          member_type=member_type,
                                          member_status=member_status)
    session.add(member)
    return member


def update_member(session, member_id, grid_id, member_name, member_ip,
                  member_ipv6, member_type, member_status):
    session.query(ib_models.InfobloxGridMember).\
        filter_by(member_id=member_id).\
        update({'grid_id': grid_id,
                'member_name': member_name,
                'member_ip': member_ip,
                'member_ipv6': member_ipv6,
                'member_type': member_type,
                'member_status': member_status})


def remove_members(session, member_ids):
    if member_ids and isinstance(member_ids, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxGridMember)
            q = q.filter(
                ib_models.InfobloxGridMember.member_id.in_(member_ids))
            q.delete()


@db_api.retry_db_errors
def get_available_member_for_network(session, grid_id, member_type=None):
    """Returns available members."""
    sub_qry = session.query(ib_models.InfobloxMemberMapping.member_id)
    q = session.query(ib_models.InfobloxGridMember)
    q = q.filter(~ib_models.InfobloxGridMember.member_id.in_(sub_qry))
    q = q.filter_by(grid_id=grid_id,
                    member_status=ib_const.MEMBER_STATUS_ON)
    if member_type:
        q = q.filter_by(member_type=member_type)
    q = q.with_lockmode("update").enable_eagerloads(False).first()
    return q


#  MEMBER Mapping
##############################################################################
def get_reserved_members_for_network(session, member_id=None, mapping_id=None,
                                     mapping_scope=None,
                                     allow_member_detail=False):
    """Returns reserved members."""
    if allow_member_detail:
        q = session.query(ib_models.InfobloxMemberMapping,
                          ib_models.InfobloxGridMember).\
            join(ib_models.InfobloxGridMember)
    else:
        q = session.query(ib_models.InfobloxMemberMapping)

    if member_id:
        q = q.filter(ib_models.InfobloxMemberMapping.member_id == member_id)
    if mapping_id:
        q = q.filter(ib_models.InfobloxMemberMapping.mapping_id == mapping_id)
    if mapping_scope:
        q = q.filter(ib_models.InfobloxMemberMapping.mapping_scope ==
                     mapping_scope)
    return q.all()


def reserve_member_for_network(session, member_id, mapping_id, mapping_scope,
                               mapping_relation):
    member = ib_models.InfobloxMemberMapping(
        member_id=member_id,
        mapping_id=mapping_id,
        mapping_scope=mapping_scope,
        mapping_relation=mapping_relation)
    session.add(member)
    return member


@db_api.retry_db_errors
def release_member_for_network(session, member_id):
    session.query(ib_models.InfobloxMemberMapping).\
        filter_by(member_id=member_id).delete()


def is_member_in_use_for_network(session, member_id):
    """Returns registered members."""
    q = session.query(ib_models.InfobloxMemberMapping)
    return q.filter_by(member_id=member_id).count() > 0


# DHCP/DNS services
##############################################################################
def get_members_for_services(session, member_id=None, service=None,
                             network_id=None):
    q = session.query(ib_models.InfobloxMemberService)
    if member_id:
        q = q.filter(ib_models.InfobloxMemberService.member_id == member_id)
    if service:
        q = q.filter(ib_models.InfobloxMemberService.service == service)
    if network_id:
        q = q.filter(ib_models.InfobloxMemberService.network_id == network_id)
    return q.all()


def add_member_for_service(session, member_id, service, network_id):
    member = ib_models.InfobloxMemberService(member_id=member_id,
                                             service=service,
                                             network_id=network_id)
    session.add(member)
    return member


def remove_member_for_service(session, member_id=None, service=None,
                              network_id=None):
    q = session.query(ib_models.InfobloxMemberService)
    if member_id:
        q = q.filter(ib_models.InfobloxMemberService.member_id == member_id)
    if service:
        q = q.filter(ib_models.InfobloxMemberService.service == service)
    if network_id:
        q = q.filter(ib_models.InfobloxMemberService.network_id == network_id)
    q.delete()


# Network view
##############################################################################
def get_network_view(session, network_id):
    q = session.query(ib_models.InfobloxNetworkView)
    net_view = q.filter_by(network_id=network_id).first()
    if net_view:
        return net_view.network_view
    return None


def associate_network_view(session, network_view, network_id):
    # there should be only one NIOS network view per Openstack network
    q = session.query(ib_models.InfobloxNetworkView)
    db_net_view = q.filter_by(network_id=network_id).first()
    if not db_net_view:
        ib_net_view = ib_models.InfobloxNetworkView(network_id=network_id,
                                                    network_view=network_view)
        session.add(ib_net_view)


def dissociate_network_view(session, network_id):
    q = session.query(ib_models.InfobloxNetworkView)
    q.filter_by(network_id=network_id).delete()


# Management Network
##############################################################################
def add_management_ip(session, network_id, fixed_ip, ip_version,
                      fixed_ip_ref):
    mgmt_ip = ib_models.InfobloxManagementNetwork(
        network_id=network_id,
        ip_address=fixed_ip,
        ip_version=ip_version,
        ip_address_ref=fixed_ip_ref)
    session.add(mgmt_ip)
    return mgmt_ip


def delete_management_ip(session, network_id):
    q = session.query(ib_models.InfobloxManagementNetwork)
    q.filter_by(network_id=network_id).delete()


def get_management_ip(session, network_id):
    q = session.query(ib_models.InfobloxManagementNetwork)
    return q.filter_by(network_id=network_id).first()


# Neutron general queries
##############################################################################
def get_network(session, network_id):
    q = session.query(models_v2.Network)
    return q.filter_by(id=network_id).one()


def get_network_by_subnet(session, subnet_id):
    sub_qry = session.query(models_v2.Subnet.network_id).\
        filter_by(id == subnet_id)
    q = session.query(ib_models.InfobloxGridMember)
    q = q.filter(models_v2.Network.id.in_(sub_qry))
    return q.one()


def get_network_name(session, subnet):
    q = session.query(models_v2.Network)
    net_name = q.join(models_v2.Subnet).filter(
        models_v2.Subnet.id == subnet['id']).first()
    if net_name:
        return net_name.name
    return None


def get_subnet(session, subnet_id):
    q = session.query(models_v2.Subnet)
    return q.filter_by(id=subnet_id).one()


def get_subnets_by_network(session, network_id):
    q = session.query(models_v2.Subnet)
    return q.filter_by(network_id=network_id).all()


def get_subnets_by_port(session, port_id):
    allocs = (session.query(models_v2.IPAllocation).
              join(models_v2.Port).
              filter_by(id=port_id)
              .all())
    subnets = []
    q = session.query(models_v2.Subnet)
    for allocation in allocs:
        subnets.append(q.
                       filter_by(id=allocation.subnet_id).
                       first())
    return subnets


def is_last_subnet(session, subnet_id):
    q = session.query(models_v2.Subnet)
    return q.filter(models_v2.Subnet.id != subnet_id).count() == 0


def is_last_subnet_in_network(session, subnet_id, network_id):
    q = session.query(models_v2.Subnet)
    return q.filter(models_v2.Subnet.id != subnet_id,
                    models_v2.Subnet.network_id == network_id).count() == 0


def is_last_subnet_in_tenant(session, subnet_id, tenant_id):
    q = session.query(models_v2.Subnet)
    return q.filter(models_v2.Subnet.id != subnet_id,
                    models_v2.Subnet.tenant_id == tenant_id).count() == 0


def is_last_subnet_in_private_networks(session, subnet_id):
    sub_qry = session.query(
        external_net_db.ExternalNetwork.network_id)
    q = session.query(models_v2.Subnet.id)
    q = q.filter(models_v2.Subnet.id != subnet_id)
    q = q.filter(~models_v2.Subnet.network_id.in_(sub_qry))
    return q.count() == 0


def get_port_by_id(session, port_id):
    q = session.query(models_v2.Port)
    return q.filter_by(id=port_id).one()


def get_subnet_dhcp_port_address(session, subnet_id):
    q = session.query(models_v2.IPAllocation)
    q = q.filter_by(subnet_id=subnet_id).join(models_v2.Port).\
        filter_by(device_owner='network:dhcp')
    dhcp_port = q.first()
    if dhcp_port:
        return dhcp_port.ip_address
    return None


def get_instance_id_by_floating_ip(session, floating_ip_id):
    q = session.query(l3_db.FloatingIP, models_v2.Port)
    q = q.filter(l3_db.FloatingIP.id == floating_ip_id)
    q = q.filter(models_v2.Port.id == l3_db.FloatingIP.fixed_port_id)
    result = q.first()
    if result:
        return result.Port.device_id
    return None


def delete_ip_allocation(session, network_id, subnet, ip_address):
    # delete the IP address from the IPAllocate table
    subnet_id = subnet['id']
    LOG.debug(_("Delete allocated IP %(ip_address)s "
                "(%(network_id)s/%(subnet_id)s)"), locals())
    alloc_qry = session.query(
        models_v2.IPAllocation).with_lockmode('update')
    alloc_qry.filter_by(network_id=network_id,
                        ip_address=ip_address,
                        subnet_id=subnet_id).delete()
