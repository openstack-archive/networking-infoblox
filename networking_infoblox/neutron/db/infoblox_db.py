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
def get_grids(session, grid_id=None, grid_name=None):
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
            q.delete(synchronize_session=False)


#  Grid Members
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
            q.delete(synchronize_session=False)
