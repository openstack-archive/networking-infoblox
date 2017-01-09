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

from datetime import datetime
import random
from sqlalchemy import func
from sqlalchemy.sql.expression import true

from neutron.db import address_scope_db
from neutron.db import external_net_db
from neutron.db import l3_db
from neutron.db import models_v2

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.db import infoblox_models as ib_models


# Grid Management
def get_grids(session, grid_id=None, grid_name=None, grid_status=None):
    q = session.query(ib_models.InfobloxGrid)
    if grid_id:
        q = q.filter(ib_models.InfobloxGrid.grid_id == grid_id)
    if grid_name:
        q = q.filter(ib_models.InfobloxGrid.grid_name == grid_name)
    if grid_status:
        q = q.filter(ib_models.InfobloxGrid.grid_status == grid_status)
    return q.all()


def add_grid(session, grid_id, grid_name, grid_connection, grid_status, gm_id):
    grid = ib_models.InfobloxGrid(grid_id=grid_id,
                                  grid_name=grid_name,
                                  grid_connection=grid_connection,
                                  grid_status=grid_status,
                                  gm_id=gm_id)
    session.add(grid)
    return grid


def update_grid(session, grid_id, grid_name=None, grid_connection=None,
                grid_status=None):
    update_data = dict()
    if grid_name:
        update_data['grid_name'] = grid_name
    if grid_connection:
        update_data['grid_connection'] = grid_connection
    if grid_status:
        update_data['grid_status'] = grid_status

    if update_data:
        session.query(ib_models.InfobloxGrid).\
            filter_by(grid_id=grid_id).\
            update(update_data)


def remove_grids(session, grid_ids):
    if grid_ids and isinstance(grid_ids, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxGrid)
            q = q.filter(ib_models.InfobloxGrid.grid_id.in_(grid_ids))
            q.delete(synchronize_session=False)


# Grid Members
def get_members(session, member_id=None, grid_id=None, member_name=None,
                member_type=None, member_status=None):
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


def search_members(session, member_ids=None, member_names=None,
                   member_types=None, member_statuses=None):
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
               member_ipv6, member_type, member_status, member_dhcp_ip,
               member_dhcp_ipv6, member_dns_ip, member_dns_ipv6,
               member_wapi):
    member = ib_models.InfobloxGridMember(member_id=member_id,
                                          grid_id=grid_id,
                                          member_name=member_name,
                                          member_ip=member_ip,
                                          member_ipv6=member_ipv6,
                                          member_type=member_type,
                                          member_status=member_status,
                                          member_dhcp_ip=member_dhcp_ip,
                                          member_dhcp_ipv6=member_dhcp_ipv6,
                                          member_dns_ip=member_dns_ip,
                                          member_dns_ipv6=member_dns_ipv6,
                                          member_wapi=member_wapi)
    session.add(member)
    return member


def update_member(session, member_id, grid_id, member_name=None,
                  member_ip=None, member_ipv6=None,
                  member_type=None, member_status=None,
                  member_dhcp_ip=None, member_dhcp_ipv6=None,
                  member_dns_ip=None, member_dns_ipv6=None,
                  member_wapi=None):
    update_data = dict()
    if member_name:
        update_data['member_name'] = member_name
    if member_ip:
        update_data['member_ip'] = member_ip
    if member_ipv6:
        update_data['member_ipv6'] = member_ipv6
    if member_type:
        update_data['member_type'] = member_type
    if member_status:
        update_data['member_status'] = member_status
    if member_dhcp_ip:
        update_data['member_dhcp_ip'] = member_dhcp_ip
    if member_dhcp_ipv6:
        update_data['member_dhcp_ipv6'] = member_dhcp_ipv6
    if member_dns_ip:
        update_data['member_dns_ip'] = member_dns_ip
    if member_dns_ipv6:
        update_data['member_dns_ipv6'] = member_dns_ipv6
    if member_wapi:
        update_data['member_wapi'] = member_wapi

    if update_data:
        session.query(ib_models.InfobloxGridMember).\
            filter_by(member_id=member_id, grid_id=grid_id).\
            update(update_data)


def remove_members(session, member_ids):
    if member_ids and isinstance(member_ids, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxGridMember)
            q = q.filter(ib_models.InfobloxGridMember.member_id.in_(
                         member_ids))
            q.delete(synchronize_session=False)


# Network Views
def get_network_views(session, network_view_id=None, network_view=None,
                      grid_id=None, authority_member_id=None, shared=None,
                      dns_view=None, internal_network_view=None,
                      internal_dns_view=None, participated=None):
    q = session.query(ib_models.InfobloxNetworkView)
    if network_view_id:
        q = q.filter(ib_models.InfobloxNetworkView.id == network_view_id)
    if network_view:
        q = q.filter(ib_models.InfobloxNetworkView.network_view ==
                     network_view)
    if authority_member_id:
        q = q.filter(ib_models.InfobloxNetworkView.authority_member_id ==
                     authority_member_id)
    if shared:
        q = q.filter(ib_models.InfobloxNetworkView.shared == shared)
    if participated:
        q = q.filter(ib_models.InfobloxNetworkView.participated ==
                     participated)
    if dns_view:
        q = q.filter(ib_models.InfobloxNetworkView.dns_view == dns_view)
    if internal_network_view:
        q = q.filter(ib_models.InfobloxNetworkView.internal_network_view ==
                     internal_network_view)
    if internal_dns_view:
        q = q.filter(ib_models.InfobloxNetworkView.internal_dns_view ==
                     internal_dns_view)
    if grid_id:
        q = q.filter(ib_models.InfobloxNetworkView.grid_id == grid_id)
    return q.all()


def get_network_view_by_mapping(session, network_view_id=None, grid_id=None,
                                network_id=None, subnet_id=None):
    netview_mapping = get_network_view_mappings(
        session,
        network_view_id=network_view_id,
        network_id=network_id,
        subnet_id=subnet_id)
    if not netview_mapping:
        return None

    if len(netview_mapping) > 1:
        raise exc.MultipleNetworkViewMappingFound()

    netview_id = netview_mapping[0].network_view_id
    netviews = get_network_views(
        session,
        network_view_id=netview_id,
        grid_id=grid_id,
        participated=True)
    return netviews


def update_network_view(session, network_view_id, network_view,
                        authority_member_id, shared, dns_view, participated,
                        is_default):
    (session.query(ib_models.InfobloxNetworkView).
     filter_by(id=network_view_id).
     update({'network_view': network_view,
             'authority_member_id': authority_member_id,
             'shared': shared,
             'dns_view': dns_view,
             'participated': participated,
             'default': is_default}))


def update_network_view_id(session, old_id, new_id):
    (session.query(ib_models.InfobloxNetworkView).
     filter_by(id=old_id).
     update({'id': new_id}))


def add_network_view(session, network_view_id, network_view, grid_id,
                     authority_member_id, shared, dns_view,
                     internal_network_view, internal_dns_view, participated,
                     is_default):
    network_view = ib_models.InfobloxNetworkView(
        id=network_view_id,
        network_view=network_view,
        grid_id=grid_id,
        authority_member_id=authority_member_id,
        shared=shared,
        dns_view=dns_view,
        internal_network_view=internal_network_view,
        internal_dns_view=internal_dns_view,
        participated=participated,
        default=is_default)
    session.add(network_view)
    session.flush()
    return network_view


def remove_network_views(session, ids):
    if ids and isinstance(ids, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxNetworkView)
            q = q.filter(ib_models.InfobloxNetworkView.id.in_(ids))
            q.delete(synchronize_session=False)


def remove_network_views_by_names(session, network_views, grid_id):
    if network_views and isinstance(network_views, list):
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxNetworkView)
            q = q.filter(ib_models.InfobloxNetworkView.grid_id == grid_id)
            q = q.filter(ib_models.InfobloxNetworkView.network_view.in_(
                         network_views))
            q.delete(synchronize_session=False)


# Network View Mapped to Neutron
def get_network_view_mappings(session, network_view_id=None, network_id=None,
                              subnet_id=None):
    q = session.query(ib_models.InfobloxNetworkViewMapping)
    if network_view_id:
        q = q.filter(ib_models.InfobloxNetworkViewMapping.network_view_id ==
                     network_view_id)
    if network_id:
        q = q.filter(ib_models.InfobloxNetworkViewMapping.network_id ==
                     network_id)
    if subnet_id:
        q = q.filter(ib_models.InfobloxNetworkViewMapping.subnet_id ==
                     subnet_id)

    sub_qry = session.query(ib_models.InfobloxNetworkView.id)
    sub_qry = sub_qry.filter(ib_models.InfobloxNetworkView.participated ==
                             true())
    q = q.filter(ib_models.InfobloxNetworkViewMapping.network_view_id.in_(
                 sub_qry))
    return q.all()


def associate_network_view(session, network_view_id, network_id, subnet_id):
    # check if network and subnet level mapping exists
    q = session.query(ib_models.InfobloxNetworkViewMapping)
    network_view_mapping = q.filter_by(network_id=network_id,
                                       subnet_id=subnet_id).first()
    if not network_view_mapping:
        network_view_mapping = ib_models.InfobloxNetworkViewMapping(
            network_view_id=network_view_id,
            network_id=network_id,
            subnet_id=subnet_id)
        session.add(network_view_mapping)


def dissociate_network_view(session, network_id, subnet_id):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxNetworkViewMapping)
        q = q.filter_by(network_id=network_id, subnet_id=subnet_id)
        q.delete(synchronize_session=False)


# Mapping Conditions
def get_mapping_conditions(session, network_view_id=None, grid_id=None,
                           neutron_object_name=None,
                           neutron_object_value=None):
    q = session.query(ib_models.InfobloxMappingCondition)
    if network_view_id:
        q = q.filter(ib_models.InfobloxMappingCondition.network_view_id ==
                     network_view_id)
    if neutron_object_name:
        q = q.filter(ib_models.InfobloxMappingCondition.neutron_object_name ==
                     neutron_object_name)
    if neutron_object_value:
        q = q.filter(ib_models.InfobloxMappingCondition.neutron_object_value ==
                     neutron_object_value)
    if grid_id:
        sub_qry = session.query(ib_models.InfobloxNetworkView.id)
        sub_qry = sub_qry.filter(ib_models.InfobloxNetworkView.grid_id ==
                                 grid_id)
        q = q.filter(ib_models.InfobloxMappingCondition.network_view_id.in_(
                     sub_qry))
    return q.all()


def add_mapping_condition(session, network_view_id, neutron_object_name,
                          neutron_object_value):
    mapping_condition = ib_models.InfobloxMappingCondition(
        network_view_id=network_view_id,
        neutron_object_name=neutron_object_name,
        neutron_object_value=neutron_object_value)
    session.add(mapping_condition)
    return mapping_condition


def add_mapping_conditions(session, network_view_id, neutron_object_name,
                           neutron_object_values):
    mapping_conditions = []
    if neutron_object_values and isinstance(neutron_object_values, list):
        for value in neutron_object_values:
            mapping_condition = ib_models.InfobloxMappingCondition(
                network_view_id=network_view_id,
                neutron_object_name=neutron_object_name,
                neutron_object_value=value
            )
            session.add(mapping_condition)
            mapping_conditions.append(mapping_condition)
    return mapping_conditions


def remove_mapping_condition(session, network_view_id, neutron_object_name,
                             neutron_object_value):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxMappingCondition)
        q = q.filter(ib_models.InfobloxMappingCondition.network_view_id ==
                     network_view_id)
        q = q.filter(ib_models.InfobloxMappingCondition.neutron_object_name ==
                     neutron_object_name)
        q = q.filter(ib_models.InfobloxMappingCondition.neutron_object_value ==
                     neutron_object_value)
        q.delete(synchronize_session=False)


def remove_mapping_conditions(session, network_view_id, neutron_object_name,
                              neutron_object_values):
    if network_view_id:
        with session.begin(subtransactions=True):
            q = session.query(ib_models.InfobloxMappingCondition)
            q = q.filter(ib_models.InfobloxMappingCondition.network_view_id ==
                         network_view_id)
            if neutron_object_name:
                q = q.filter(ib_models.InfobloxMappingCondition.
                             neutron_object_name == neutron_object_name)
            if (neutron_object_values and
                    isinstance(neutron_object_values, list)):
                q = q.filter(ib_models.InfobloxMappingCondition.
                             neutron_object_value.in_(neutron_object_values))
            q.delete(synchronize_session=False)


# Mapping Members
def get_mapping_members(session, network_view_id=None, member_id=None,
                        grid_id=None, mapping_relation=None):
    q = session.query(ib_models.InfobloxMappingMember)
    if network_view_id:
        q = q.filter(ib_models.InfobloxMappingMember.network_view_id ==
                     network_view_id)
    if member_id:
        q = q.filter(ib_models.InfobloxMappingMember.member_id == member_id)
    if mapping_relation:
        q = q.filter(ib_models.InfobloxMappingMember.mapping_relation ==
                     mapping_relation)
    if grid_id:
        sub_qry = session.query(ib_models.InfobloxNetworkView.id)
        sub_qry = sub_qry.filter(ib_models.InfobloxNetworkView.grid_id ==
                                 grid_id)
        q = q.filter(ib_models.InfobloxMappingMember.network_view_id.in_(
                     sub_qry))
    return q.all()


def add_mapping_member(session, network_view_id, member_id, mapping_relation):
    mapping_member = ib_models.InfobloxMappingMember(
        network_view_id=network_view_id,
        member_id=member_id,
        mapping_relation=mapping_relation)
    session.add(mapping_member)
    return mapping_member


def update_mapping_member(session, network_view_id, member_id,
                          mapping_relation):
    session.query(ib_models.InfobloxMappingMember).\
        filter_by(network_view_id=network_view_id, member_id=member_id).\
        update({'mapping_relation': mapping_relation})


def remove_mapping_member(session, network_view_id, member_id):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxMappingMember)
        q = q.filter_by(network_view_id=network_view_id, member_id=member_id)
        q.delete(synchronize_session=False)


# Member Reservation
def get_next_authority_member_for_ipam(session, grid_id):
    q = (session.query(
         ib_models.InfobloxGridMember,
         ib_models.InfobloxGridMember.member_id,
         func.count(ib_models.InfobloxNetworkView.id).label('count')).
         outerjoin(ib_models.InfobloxNetworkView,
                   ib_models.InfobloxNetworkView.authority_member_id ==
                   ib_models.InfobloxGridMember.member_id).
         filter(ib_models.InfobloxGridMember.grid_id == grid_id,
                ib_models.InfobloxGridMember.member_status ==
                const.MEMBER_STATUS_ON,
                ib_models.InfobloxGridMember.member_type !=
                const.MEMBER_TYPE_REGULAR_MEMBER).
         group_by(ib_models.InfobloxNetworkView.authority_member_id).
         order_by('count'))
    res = q.first()
    authority_member = res[0]
    return authority_member


def get_next_authority_member_for_dhcp(session, grid_id):
    q = (session.query(ib_models.InfobloxGridMember).
         outerjoin(ib_models.InfobloxMappingMember,
                   ib_models.InfobloxMappingMember.member_id ==
                   ib_models.InfobloxGridMember.member_id).
         outerjoin(ib_models.InfobloxServiceMember,
                   ib_models.InfobloxServiceMember.member_id ==
                   ib_models.InfobloxGridMember.member_id).
         filter(ib_models.InfobloxGridMember.grid_id == grid_id,
                ib_models.InfobloxGridMember.member_status ==
                const.MEMBER_STATUS_ON,
                ib_models.InfobloxGridMember.member_type ==
                const.MEMBER_TYPE_CP_MEMBER,
                ib_models.InfobloxMappingMember.member_id.is_(None),
                ib_models.InfobloxServiceMember.member_id.is_(None)))
    row_count = int(q.count())
    q = q.offset(int(row_count * random.random()))
    authority_member = q.first()
    return authority_member


def get_next_dhcp_member(session, grid_id, use_gm=True):
    """Get a next available dhcp member.

    For dhcp member, any member can be chosen but the priority is given to
    REGUALR first, then CPM. However gm can be omitted from selection
    if 'use_gm' parameter is set to False.
    """
    q = (session.query(ib_models.InfobloxGridMember).
         outerjoin(ib_models.InfobloxMappingMember,
                   ib_models.InfobloxMappingMember.member_id ==
                   ib_models.InfobloxGridMember.member_id).
         outerjoin(ib_models.InfobloxServiceMember,
                   ib_models.InfobloxServiceMember.member_id ==
                   ib_models.InfobloxGridMember.member_id).
         filter(ib_models.InfobloxGridMember.grid_id == grid_id,
                ib_models.InfobloxGridMember.member_status ==
                const.MEMBER_STATUS_ON,
                ib_models.InfobloxMappingMember.member_id.is_(None),
                ib_models.InfobloxServiceMember.member_id.is_(None)))
    if use_gm is False:
        q = q.filter(ib_models.InfobloxGridMember.member_type !=
                     const.MEMBER_TYPE_GRID_MASTER)
    q = q.order_by(ib_models.InfobloxGridMember.member_type.desc())
    row_count = int(q.count())
    q = q.offset(int(row_count * random.random()))
    dhcp_member = q.first()
    return dhcp_member


# Service Member Management
def get_service_members(session, network_view_id=None, member_id=None,
                        grid_id=None, service=None):
    q = session.query(ib_models.InfobloxServiceMember)
    if network_view_id:
        q = q.filter(ib_models.InfobloxServiceMember.network_view_id ==
                     network_view_id)
    if member_id:
        q = q.filter(ib_models.InfobloxServiceMember.member_id == member_id)
    if service:
        q = q.filter(ib_models.InfobloxServiceMember.service == service)
    if grid_id:
        sub_qry = (session.query(ib_models.InfobloxGridMember.member_id).
                   filter(ib_models.InfobloxGridMember.grid_id == grid_id))
        q = q.filter(ib_models.InfobloxServiceMember.member_id.in_(sub_qry))
    return q.all()


def add_service_member(session, network_view_id, member_id, service):
    service_member = ib_models.InfobloxServiceMember(
        network_view_id=network_view_id,
        member_id=member_id,
        service=service)
    session.add(service_member)
    return service_member


def remove_service_member(session, network_view_id, member_id=None,
                          service=None):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxServiceMember)
        q = q.filter(ib_models.InfobloxServiceMember.network_view_id ==
                     network_view_id)
        if member_id:
            q = q.filter(ib_models.InfobloxServiceMember.member_id ==
                         member_id)
        if service:
            q = q.filter(ib_models.InfobloxServiceMember.service == service)
        q.delete(synchronize_session=False)


def remove_service_members(session, network_view_id, member_ids):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxServiceMember)
        q = q.filter(ib_models.InfobloxServiceMember.network_view_id ==
                     network_view_id)
        if member_ids and isinstance(member_ids, list):
            q = q.filter(ib_models.InfobloxServiceMember.member_id.in_(
                         member_ids))
        q.delete(synchronize_session=False)


# Operational Setting Management
def add_operation_type(session, op_type, op_value):
    operation = ib_models.InfobloxOperation(
        op_type=op_type,
        op_value=op_value)
    session.add(operation)
    return operation


def get_last_sync_time(session):
    q = session.query(ib_models.InfobloxOperation)
    op_row = q.filter_by(op_type='last_sync_time').first()
    if op_row is None:
        add_operation_type(session, op_type='last_sync_time', op_value='')
        return None
    if op_row.op_value == '':
        return None
    return datetime.strptime(op_row.op_value, "%Y-%m-%d %H:%M:%S")


def record_last_sync_time(session, sync_time=None):
    if sync_time is None:
        sync_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    else:
        sync_time_str = sync_time.strftime("%Y-%m-%d %H:%M:%S")

    session.query(ib_models.InfobloxOperation).\
        filter_by(op_type='last_sync_time').\
        update({'op_value': sync_time_str})


# Neutron General Queries
def get_subnets_by_network_id(session, network_id):
    q = session.query(models_v2.Subnet).filter_by(network_id=network_id)
    return q.all()


def get_subnet_by_id(session, subnet_id):
    q = session.query(models_v2.Subnet).filter_by(id=subnet_id)
    return q.one()


def get_subnets_by_tenant_id(session, tenant_id):
    q = session.query(models_v2.Subnet).filter_by(tenant_id=tenant_id)
    return q.all()


def get_port_by_id(session, port_id):
    q = session.query(models_v2.Port)
    return q.filter_by(id=port_id).one()


def get_subnet_dhcp_port_address(session, subnet_id):
    dhcp_port = (session.query(models_v2.IPAllocation).
                 filter_by(subnet_id=subnet_id).
                 join(models_v2.Port).
                 filter_by(device_owner='network:dhcp')
                 .first())
    if dhcp_port:
        return dhcp_port.ip_address
    return None


def get_floatingip_by_id(session, floatingip_id):
    q = session.query(l3_db.FloatingIP)
    return q.filter_by(id=floatingip_id).one()


def get_floatingip_by_ip_address(session, floatingip):
    q = session.query(l3_db.FloatingIP)
    return q.filter_by(floating_ip_address=floatingip).one()


def get_address_scope_by_subnetpool_id(session, subnetpool_id):
    sub_qry = (session.query(models_v2.SubnetPool.address_scope_id).
               filter(models_v2.SubnetPool.id == subnetpool_id))
    q = (session.query(address_scope_db.AddressScope).
         filter(address_scope_db.AddressScope.id.in_(sub_qry)))
    return q.first()


def is_last_subnet(session, subnet_id):
    q = (session.query(models_v2.Subnet).
         filter(models_v2.Subnet.id != subnet_id))
    return q.count() == 0


def is_last_subnet_in_network(session, subnet_id, network_id):
    q = (session.query(models_v2.Subnet).
         filter(models_v2.Subnet.id != subnet_id,
                models_v2.Subnet.network_id == network_id))
    return q.count() == 0


def is_last_subnet_in_tenant(session, subnet_id, tenant_id):
    q = (session.query(models_v2.Subnet).
         filter(models_v2.Subnet.id != subnet_id,
                models_v2.Subnet.tenant_id == tenant_id))
    return q.count() == 0


def is_last_subnet_in_private_networks(session, subnet_id):
    sub_qry = session.query(external_net_db.ExternalNetwork.network_id)
    q = (session.query(models_v2.Subnet.id).
         filter(models_v2.Subnet.id != subnet_id).
         filter(~models_v2.Subnet.network_id.in_(sub_qry)))
    return q.count() == 0


def is_last_subnet_in_address_scope(session, subnet_id):
    q = (session.query(models_v2.Subnet).
         filter(models_v2.Subnet.subnetpool_id == models_v2.SubnetPool.id).
         filter(address_scope_db.id == models_v2.SubnetPool.address_scope_id).
         filter(models_v2.Subnet.id != subnet_id))
    return q.count() == 0


def add_tenant(session, tenant_id, tenant_name):
    tenant = ib_models.InfobloxTenant(
        tenant_id=tenant_id,
        tenant_name=tenant_name)
    session.add(tenant)
    return tenant


def add_or_update_tenant(session, tenant_id, tenant_name):
    db_tenant = get_tenant(session, tenant_id)
    if db_tenant is None:
        add_tenant(session, tenant_id, tenant_name)
    elif db_tenant.tenant_name != tenant_name:
        db_tenant.tenant_name = tenant_name


def get_tenant(session, tenant_id):
    q = session.query(ib_models.InfobloxTenant)
    return q.filter_by(tenant_id=tenant_id).first()


def get_tenants(session, tenant_ids=None):
    q = session.query(ib_models.InfobloxTenant)
    if tenant_ids:
        q = q.filter(ib_models.InfobloxTenant.tenant_id.in_(tenant_ids))
    return q.all()


def get_external_subnets(session):
    sub_qry = session.query(external_net_db.ExternalNetwork.network_id)
    return (session.query(models_v2.Subnet).
            filter(models_v2.Subnet.network_id.in_(sub_qry))).all()


def get_floatingip_ports(session, floating_ips, floating_network_id):
    q = (session.query(models_v2.Port.id,
                       models_v2.Port.device_id,
                       models_v2.Port.device_owner,
                       l3_db.FloatingIP.floating_ip_address,
                       models_v2.Port.name).
         filter(models_v2.Port.id == l3_db.FloatingIP.floating_port_id).
         filter(l3_db.FloatingIP.floating_ip_address.in_(floating_ips)))
    return q.all()


def add_instance(session, instance_id, instance_name):
    instance = ib_models.InfobloxInstance(
        instance_id=instance_id,
        instance_name=instance_name)
    session.add(instance)
    return instance


def add_or_update_instance(session, instance_id, instance_name):
    db_instance = get_instance(session, instance_id)
    if db_instance is None:
        add_instance(session, instance_id, instance_name)
    elif db_instance.instance_name != instance_name:
        db_instance.instance_name = instance_name


def get_instance(session, instance_id):
    q = session.query(ib_models.InfobloxInstance)
    return q.filter_by(instance_id=instance_id).first()


def remove_instance(session, instance_id):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxInstance)
        q = q.filter_by(instance_id=instance_id)
        q.delete(synchronize_session=False)


def get_instances(session, instance_ids=None):
    q = session.query(ib_models.InfobloxInstance)
    if instance_ids:
        q = q.filter(ib_models.InfobloxInstance.instance_id.in_(instance_ids))
    return q.all()


def add_network(session, network_id, network_name):
    network = ib_models.InfobloxNetwork(
        network_id=network_id,
        network_name=network_name)
    session.add(network)
    return network


def add_or_update_network(session, network_id, network_name):
    db_network = get_network(session, network_id)
    if db_network is None:
        add_network(session, network_id, network_name)
    elif db_network.network_name != network_name:
        db_network.network_name = network_name


def get_network(session, network_id):
    q = session.query(ib_models.InfobloxNetwork)
    return q.filter_by(network_id=network_id).first()


def remove_network(session, network_id):
    with session.begin(subtransactions=True):
        q = session.query(ib_models.InfobloxNetwork)
        q = q.filter_by(network_id=network_id)
        q.delete(synchronize_session=False)
