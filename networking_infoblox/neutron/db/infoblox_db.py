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

from networking_infoblox.neutron.db import infoblox_models as ib_models


LOG = logging.getLogger(__name__)


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


def add_grid(session, grid_id, grid_name, grid_connection, grid_status):
    grid = ib_models.InfobloxGrid(grid_id=grid_id,
                                  grid_name=grid_name,
                                  grid_connection=grid_connection,
                                  grid_status=grid_status)
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


def update_member(session, member_id, grid_id, member_name=None,
                  member_ip=None, member_ipv6=None, member_type=None,
                  member_status=None):
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
def get_network_views(session, network_view=None, grid_id=None):
    q = session.query(ib_models.InfobloxNetworkView)
    if network_view:
        q = q.filter(ib_models.InfobloxNetworkView.network_view ==
                     network_view)
    if grid_id:
        q = q.filter(ib_models.InfobloxNetworkView.grid_id == grid_id)
    return q.all()


def add_network_view(session, network_view, grid_id):
    network_view = ib_models.InfobloxNetworkView(network_view=network_view,
                                                 grid_id=grid_id)
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
