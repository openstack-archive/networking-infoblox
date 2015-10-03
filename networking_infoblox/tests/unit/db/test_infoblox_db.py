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

from oslo_serialization import jsonutils

from neutron import context
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db


class InfobloxDbTestCase(testlib_api.SqlTestCase):

    def setUp(self):
        super(InfobloxDbTestCase, self).setUp()
        self.ctx = context.get_admin_context()
        self.grid_id = 100
        self.grid_name = "Test Grid 1000"
        self.grid_connection = "{}"
        self.grid_status = "ON"

    def _create_default_grid(self):
        infoblox_db.add_grid(self.ctx.session, self.grid_id, self.grid_name,
                             self.grid_connection, self.grid_status)
        self.ctx.session.flush()

    def _create_grids(self, grid_list):
        for grid in grid_list:
            infoblox_db.add_grid(self.ctx.session, grid['grid_id'],
                                 grid['grid_name'], grid['grid_connection'],
                                 grid['grid_status'])

    def test_grid_management(self):
        grid_list = [{'grid_id': 100,
                      'grid_name': 'Test Grid 1000',
                      'grid_connection': '{}',
                      'grid_status': 'ON'},
                     {'grid_id': 200,
                      'grid_name': 'Test Grid 2000',
                      'grid_connection': '{}',
                      'grid_status': 'OFF'}]

        # expects no grid
        db_grids = infoblox_db.get_grids(self.ctx.session)
        self.assertEqual(0, len(db_grids))

        # test grid additions
        self._create_grids(grid_list)

        db_grids = infoblox_db.get_grids(self.ctx.session)
        actual_grid_rows = utils.get_composite_values_from_records(
            ['grid_id', 'grid_name', 'grid_connection', 'grid_status'],
            db_grids)
        expected_grid_rows = utils.get_composite_values_from_records(
            ['grid_id', 'grid_name', 'grid_connection', 'grid_status'],
            grid_list)
        self.assertEqual(expected_grid_rows, actual_grid_rows)

        # test grid retrieval by grid_id filter
        db_grids = infoblox_db.get_grids(self.ctx.session,
                                         grid_id=grid_list[0]['grid_id'])
        self.assertEqual(grid_list[0]['grid_id'], db_grids[0]['grid_id'])
        self.assertEqual(grid_list[0]['grid_name'], db_grids[0]['grid_name'])
        self.assertEqual(grid_list[0]['grid_connection'],
                         db_grids[0]['grid_connection'])
        self.assertEqual(grid_list[0]['grid_connection'],
                         db_grids[0]['grid_connection'])
        self.assertEqual(grid_list[0]['grid_status'],
                         db_grids[0]['grid_status'])

        db_grids = infoblox_db.get_grids(self.ctx.session,
                                         grid_id=grid_list[1]['grid_id'],
                                         grid_name=grid_list[0]['grid_name'])
        self.assertEqual([], db_grids)

        # test grid retrieval by grid_id and grid_name filters
        db_grids = infoblox_db.get_grids(self.ctx.session,
                                         grid_id=grid_list[1]['grid_id'],
                                         grid_name=grid_list[1]['grid_name'])
        self.assertEqual(grid_list[1]['grid_id'], db_grids[0]['grid_id'])
        self.assertEqual(grid_list[1]['grid_name'], db_grids[0]['grid_name'])
        self.assertEqual(grid_list[1]['grid_connection'],
                         db_grids[0]['grid_connection'])
        self.assertEqual(grid_list[1]['grid_connection'],
                         db_grids[0]['grid_connection'])
        self.assertEqual(grid_list[1]['grid_status'],
                         db_grids[0]['grid_status'])

        # test grid update
        grid_name_update = "Test Grid 1000 Enhanced"
        grid_connection_json = {
            "wapi_version": "2.0",
            "ssl_verify": False,
            "http_pool_connections": 100,
            "http_pool_maxsize": 100,
            "http_request_timeout": 120,
            "admin_user": {"name": "admin", "password": "infoblox"},
            "cloud_user": {"name": "cloud-api-user", "password": "infoblox"}
        }
        grid_connection_json_string = jsonutils.dumps(grid_connection_json)

        infoblox_db.update_grid(self.ctx.session,
                                grid_list[0]['grid_id'],
                                grid_name_update,
                                grid_connection_json_string)
        db_grids = infoblox_db.get_grids(self.ctx.session,
                                         grid_list[0]['grid_id'])
        self.assertEqual(grid_name_update, db_grids[0]['grid_name'])
        self.assertEqual(grid_connection_json_string,
                         db_grids[0]['grid_connection'])

        # test grid removal
        infoblox_db.remove_grids(self.ctx.session, [grid_list[0]['grid_id']])

        db_grids = infoblox_db.get_grids(self.ctx.session,
                                         grid_list[0]['grid_id'])
        self.assertEqual(0, len(db_grids))

        # remove two grids
        self._create_grids([grid_list[0]])
        infoblox_db.remove_grids(self.ctx.session,
                                 [grid_list[0]['grid_id'],
                                  grid_list[1]['grid_id']])

        db_grids = infoblox_db.get_grids(self.ctx.session)
        self.assertEqual(0, len(db_grids))

    def _create_members(self, member_list, grid_id):
        for member in member_list:
            infoblox_db.add_member(self.ctx.session,
                                   member['member_id'],
                                   grid_id,
                                   member['member_name'],
                                   member['member_ip'],
                                   member['member_ipv6'],
                                   member['member_type'],
                                   member['member_status'])

    def test_member_management(self):
        # prepare grid
        self._create_default_grid()

        member_list = [{'member_id': 'M_1000',
                        'member_name': 'Member 1000',
                        'member_ip': '10.10.1.12',
                        'member_ipv6': None,
                        'member_type': 'REGULAR',
                        'member_status': 'WORKING'},
                       {'member_id': 'M_2000',
                        'member_name': 'Member 2000',
                        'member_ip': '10.10.1.22',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'WORKING'}]

        # expects no member
        db_members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(0, len(db_members))

        # test member additions
        self._create_members(member_list, self.grid_id)

        db_members = infoblox_db.get_members(self.ctx.session)
        actual_member_rows = utils.get_composite_values_from_records(
            ['member_id', 'member_name', 'member_ip', 'member_ipv6',
             'member_type', 'member_status'],
            db_members)
        expected_member_rows = utils.get_composite_values_from_records(
            ['member_id', 'member_name', 'member_ip', 'member_ipv6',
             'member_type', 'member_status'],
            member_list)
        self.assertEqual(expected_member_rows, actual_member_rows)

        # test member update
        member_name_update = "Member 1000 VM"
        member_ipv6_update = "fd44:acb:5df6:1083::12"
        infoblox_db.update_member(self.ctx.session,
                                  member_list[0]['member_id'],
                                  self.grid_id,
                                  member_name=member_name_update,
                                  member_ipv6=member_ipv6_update)
        db_members = infoblox_db.get_members(self.ctx.session,
                                             member_list[0]['member_id'],
                                             grid_id=self.grid_id)
        self.assertEqual(member_name_update, db_members[0]['member_name'])
        self.assertEqual(member_ipv6_update, db_members[0]['member_ipv6'])

        # test member removals
        infoblox_db.remove_members(self.ctx.session,
                                   [member_list[0]['member_id']])
        db_members = infoblox_db.get_members(self.ctx.session,
                                             member_list[0]['member_id'])
        self.assertEqual(0, len(db_members))

        self._create_members([member_list[0]], self.grid_id)
        db_members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(2, len(db_members))

        infoblox_db.remove_members(self.ctx.session,
                                   [member_list[0]['member_id'],
                                    member_list[1]['member_id']])
        db_members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(0, len(db_members))

        infoblox_db.remove_grids(self.ctx.session, [self.grid_id])

    def _create_network_views(self, network_view_list, grid_id):
        for network_view in network_view_list:
            infoblox_db.add_network_view(self.ctx.session,
                                         network_view,
                                         grid_id)

    def test_mapping_management_network_views(self):
        # prepare grid
        self._create_default_grid()

        # should be no network views
        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        self.assertEqual(0, len(db_network_views))

        # test network view additions
        netview_list = ['default', 'hs-view-1', 'hs-view-2', 'hs-view-3']
        self._create_network_views(netview_list, self.grid_id)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        actual_rows = utils.get_values_from_records('network_view',
                                                    db_network_views)
        self.assertEqual(netview_list, actual_rows)

        # test network view removals
        # - remove 'hs-view-1', 'hs-view-2'
        removing_list = [netview_list[1], netview_list[2]]
        infoblox_db.remove_network_views_by_names(self.ctx.session,
                                                  removing_list,
                                                  self.grid_id)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        actual_rows = utils.get_values_from_records('network_view',
                                                    db_network_views)
        actual_set = set(actual_rows)
        expected_set = set(netview_list).difference(removing_list)
        self.assertEqual(expected_set, actual_set)

        # - remove 'hs-view-3'
        removing_netview_name = 'hs-view-3'
        removing_netview = utils.find_one_in_list('network_view',
                                                  removing_netview_name,
                                                  db_network_views)
        removing_netview_id = removing_netview.id
        infoblox_db.remove_network_views(self.ctx.session,
                                         [removing_netview_id])

        actual_network_views = infoblox_db.get_network_views(
            self.ctx.session, network_view=removing_netview_name)
        self.assertEqual([], actual_network_views)

    def test_mapping_management_mapping_conditions(self):
        # prepare grid
        self._create_default_grid()

        # prepare network views
        netview_list = ['default']
        self._create_network_views(netview_list, self.grid_id)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        netview_default_row = utils.find_one_in_list('network_view',
                                                     'default',
                                                     db_network_views)
        netview_id = netview_default_row.id

        # should be no conditions
        db_conditions = infoblox_db.get_mapping_conditions(self.ctx.session)
        self.assertEqual(0, len(db_conditions))

        expected_rows = []

        # test mapping condition additions
        neutron_object_name = const.EA_MAPPING_TENANT_ID
        neutron_object_value = '90fbad5a098a4b7cb98826128d5b40b3'
        expected_rows.append(netview_id + ':' + neutron_object_name +
                             ':' + neutron_object_value)
        infoblox_db.add_mapping_condition(self.ctx.session,
                                          netview_id,
                                          neutron_object_name,
                                          neutron_object_value)

        neutron_object_name = const.EA_MAPPING_TENANT_CIDR
        neutron_object_values = ["12.12.1.0/24", "13.13.1.0/24"]
        for value in neutron_object_values:
            expected_rows.append(netview_id + ':' + neutron_object_name +
                                 ':' + value)
        infoblox_db.add_mapping_conditions(self.ctx.session,
                                           netview_id,
                                           neutron_object_name,
                                           neutron_object_values)

        db_conditions = infoblox_db.get_mapping_conditions(self.ctx.session)
        actual_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'neutron_object_name', 'neutron_object_value'],
            db_conditions, ':')
        self.assertEqual(expected_rows, actual_rows)

        # test mapping condition removals
        # - remove Tenant ID Mapping condition
        condition_1 = expected_rows[0].split(':')
        condition_neutron_object_name = condition_1[1]
        condition_neutron_object_value = condition_1[2]
        infoblox_db.remove_mapping_condition(self.ctx.session,
                                             netview_id,
                                             condition_neutron_object_name,
                                             condition_neutron_object_value)

        db_conditions = infoblox_db.get_mapping_conditions(
            self.ctx.session,
            network_view_id=netview_id,
            grid_id=self.grid_id,
            neutron_object_name=condition_neutron_object_name)
        self.assertEqual([], db_conditions)

        # - remove two Tenant CIDR Mapping conditions
        condition_2 = expected_rows[1].split(':')
        condition_3 = expected_rows[2].split(':')
        condition_neutron_object_name = condition_2[1]
        condition_neutron_object_values = [condition_2[2], condition_3[2]]
        infoblox_db.remove_mapping_conditions(self.ctx.session,
                                              netview_id,
                                              condition_neutron_object_name,
                                              condition_neutron_object_values)

        db_conditions = infoblox_db.get_mapping_conditions(
            self.ctx.session,
            network_view_id=netview_id,
            grid_id=self.grid_id,
            neutron_object_name=condition_neutron_object_name)
        self.assertEqual([], db_conditions)

        db_conditions = infoblox_db.get_mapping_conditions(self.ctx.session)
        self.assertEqual([], db_conditions)

    def test_mapping_management_mapping_members(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'M_1000',
                        'member_name': 'Member 1000',
                        'member_ip': '10.10.1.12',
                        'member_ipv6': None,
                        'member_type': 'REGULAR',
                        'member_status': 'WORKING'},
                       {'member_id': 'M_2000',
                        'member_name': 'Member 2000',
                        'member_ip': '10.10.1.22',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'WORKING'}]
        self._create_members(member_list, self.grid_id)

        # prepare network views
        network_view_list = ['default']
        self._create_network_views(network_view_list, self.grid_id)

        # get network view id
        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        netview_default_row = utils.find_one_in_list('network_view',
                                                     'default',
                                                     db_network_views)
        netview_id = netview_default_row.id

        # should be no mapping members
        db_members = infoblox_db.get_mapping_members(self.ctx.session)
        self.assertEqual(0, len(db_members))

        # test mapping member additions
        expected_rows = []
        member_id = member_list[0]['member_id']
        relation = const.MAPPING_RELATION_DELEGATED
        infoblox_db.add_mapping_member(self.ctx.session, netview_id, member_id,
                                       relation)
        expected_rows.append(netview_id + ':' + member_id + ':' + relation)

        member_id = member_list[1]['member_id']
        relation = const.MAPPING_RELATION_DELEGATED
        infoblox_db.add_mapping_member(self.ctx.session, netview_id, member_id,
                                       relation)
        expected_rows.append(netview_id + ':' + member_id + ':' + relation)

        db_members = infoblox_db.get_mapping_members(self.ctx.session)
        actual_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            db_members, ':')
        self.assertEqual(expected_rows, actual_rows)

        # test mapping member update
        member_id = member_list[0]['member_id']
        relation = const.MAPPING_RELATION_GM_OWNED
        infoblox_db.update_mapping_member(self.ctx.session, netview_id,
                                          member_id, relation)
        expected_rows[0] = netview_id + ':' + member_id + ':' + relation

        db_members = infoblox_db.get_mapping_members(self.ctx.session)
        actual_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            db_members, ':')
        self.assertEqual(expected_rows, actual_rows)

        # test mapping member removals
        member_id = member_list[0]['member_id']
        infoblox_db.remove_mapping_member(self.ctx.session, netview_id,
                                          member_id)
        db_members = infoblox_db.get_mapping_members(self.ctx.session,
                                                     member_id=member_id)
        self.assertEqual([], db_members)
