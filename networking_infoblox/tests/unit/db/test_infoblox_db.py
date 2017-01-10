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
from oslo_db import exception as db_exc
from oslo_serialization import jsonutils

from neutron import context
from neutron.db import models_v2
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

    def _create_tenants(self, tenants):
        for id, name in tenants.items():
            infoblox_db.add_tenant(self.ctx.session, id, name)

    def test_add_and_get_tenant(self):
        tenants = {'tenant-id': 'tenant-name'}
        self._create_tenants(tenants)
        tenant = infoblox_db.get_tenant(self.ctx.session, 'tenant-id')
        self.assertEqual('tenant-name', tenant.tenant_name)

    def test_get_tenants(self):
        tenants = {'tenant-one': 'tenant-name-1',
                   'tenant-two': 'tenant-name-2',
                   'tenant-three': 'tenant-name-3'}
        self._create_tenants(tenants)
        tenants = infoblox_db.get_tenants(self.ctx.session,
                                          ['tenant-one', 'tenant-three'])
        self.assertEqual(2, len(tenants))

    def test_add_or_update_tenant(self):
        tenants = {'tenant-id1': 'tenant-name1'}
        self._create_tenants(tenants)
        new_tenant_name = 'tenant-name-updated'
        infoblox_db.add_or_update_tenant(self.ctx.session,
                                         'tenant-id1', new_tenant_name)
        tenant = infoblox_db.get_tenant(self.ctx.session, 'tenant-id1')
        self.assertEqual(new_tenant_name, tenant.tenant_name)

        infoblox_db.add_or_update_tenant(self.ctx.session,
                                         'tenant-id2', 'tenant-name2')
        tenant = infoblox_db.get_tenant(self.ctx.session, 'tenant-id2')
        self.assertEqual('tenant-name2', tenant.tenant_name)

    def _create_default_grid(self):
        infoblox_db.add_grid(self.ctx.session, self.grid_id, self.grid_name,
                             self.grid_connection, self.grid_status,
                             'gm-id-' + str(self.grid_id))
        self.ctx.session.flush()

    def _create_grids(self, grid_list):
        for grid in grid_list:
            infoblox_db.add_grid(self.ctx.session, grid['grid_id'],
                                 grid['grid_name'], grid['grid_connection'],
                                 grid['grid_status'],
                                 'gm-id-' + str(grid['grid_id']))

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
            "admin_user": {"name": "admin", "password": "infoblox"}
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
                                   member['member_status'],
                                   None, None, None, None,
                                   member['member_ip'])

    def test_member_management(self):
        # prepare grid
        self._create_default_grid()

        member_list = [{'member_id': 'M_1000',
                        'member_name': 'Member 1000',
                        'member_ip': '10.10.1.12',
                        'member_ipv6': None,
                        'member_type': 'REGULAR',
                        'member_status': 'ON'},
                       {'member_id': 'M_2000',
                        'member_name': 'Member 2000',
                        'member_ip': '10.10.1.22',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'ON'}]

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

    def _create_network_views(self, network_view_dict):
        netview_count = 1
        for network_view in network_view_dict:
            is_default = True if network_view == 'default' else False
            dns_view = ('default' if network_view == 'default' else
                        'default.' + network_view)
            netview_id = 'netview-id-' + str(netview_count)
            infoblox_db.add_network_view(self.ctx.session,
                                         netview_id,
                                         network_view,
                                         self.grid_id,
                                         network_view_dict[network_view],
                                         False,
                                         dns_view,
                                         network_view,
                                         dns_view,
                                         True,
                                         is_default)
            netview_count += 1

    def _create_simple_members(self):
        for i in range(1, 6):
            member_id = "mid%d" % i
            member_name = 'member%d.test.com' % i
            member_ipv4 = "10.10.1.%d" % i
            member_type = "GM" if i == 1 else "CPM"
            infoblox_db.add_member(self.ctx.session, member_id, self.grid_id,
                                   member_name, member_ipv4, None, member_type,
                                   'ON', None, None, None, None, member_ipv4)

    def test_network_view_management(self):
        # prepare grid
        self._create_default_grid()

        # prepare members
        self._create_simple_members()
        db_members = infoblox_db.get_members(self.ctx.session)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)

        # should be no network views
        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        self.assertEqual(0, len(db_network_views))

        # test network view additions
        netview_dict = {'default': gm_member.member_id,
                        'hs-view-1': gm_member.member_id,
                        'hs-view-2': gm_member.member_id,
                        'hs-view-3': gm_member.member_id}
        self._create_network_views(netview_dict)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        actual_rows = utils.get_values_from_records('network_view',
                                                    db_network_views)
        self.assertEqual(netview_dict.keys(), actual_rows)

        # test network view removals
        # - remove 'hs-view-1', 'hs-view-2'
        removing_list = [netview_dict['hs-view-1'], netview_dict['hs-view-2']]
        infoblox_db.remove_network_views_by_names(self.ctx.session,
                                                  removing_list,
                                                  self.grid_id)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        actual_rows = utils.get_values_from_records('network_view',
                                                    db_network_views)
        actual_set = set(actual_rows)
        expected_set = set(netview_dict.keys()).difference(removing_list)
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

    def test_network_view_mapping(self):
        # prepare grid
        self._create_default_grid()

        # prepare members
        self._create_simple_members()
        db_members = infoblox_db.get_members(self.ctx.session)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)

        # prepare network
        network = models_v2.Network(name="Test Network", status="ON",
                                    admin_state_up=True)
        self.ctx.session.add(network)
        self.ctx.session.flush()

        # prepare network view
        netview_dict = {'hs-view-1': gm_member.member_id}
        self._create_network_views(netview_dict)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        network_view_id = db_network_views[0].id

        # test associate network view
        network_id = network.id
        subnet_id = 'test-subnet-id'
        infoblox_db.associate_network_view(self.ctx.session, network_view_id,
                                           network_id, subnet_id)
        db_network_view_mappings = infoblox_db.get_network_view_mappings(
            self.ctx.session)
        self.assertEqual(network_id, db_network_view_mappings[0].network_id)
        self.assertEqual(subnet_id, db_network_view_mappings[0].subnet_id)

        db_network_views = infoblox_db.get_network_view_by_mapping(
            self.ctx.session,
            network_id=network_id,
            subnet_id=subnet_id)
        self.assertEqual(network_view_id, db_network_views[0].id)

        # test dissociate network view
        infoblox_db.dissociate_network_view(self.ctx.session, network_id,
                                            subnet_id)
        db_network_view_mappings = infoblox_db.get_network_view_mappings(
            self.ctx.session, network_id=network_id, subnet_id=subnet_id)
        self.assertEqual([], db_network_view_mappings)

    def test_mapping_management_mapping_conditions(self):
        # prepare grid
        self._create_default_grid()

        # prepare members
        self._create_simple_members()
        db_members = infoblox_db.get_members(self.ctx.session)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)

        # prepare network views
        netview_dict = {'default': gm_member.member_id}
        self._create_network_views(netview_dict)

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

        neutron_object_name = const.EA_MAPPING_SUBNET_CIDR
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
        self._create_simple_members()
        db_members = infoblox_db.get_members(self.ctx.session)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)

        # prepare network views
        netview_dict = {'default': gm_member.member_id}
        self._create_network_views(netview_dict)

        # get network view id
        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        netview_default_row = utils.find_one_in_list('network_view',
                                                     'default',
                                                     db_network_views)
        netview_id = netview_default_row.id

        # should be no mapping members
        db_mapping_members = infoblox_db.get_mapping_members(self.ctx.session)
        self.assertEqual(0, len(db_mapping_members))

        # test mapping member additions
        expected_rows = []
        member_id = db_members[0]['member_id']
        relation = const.MAPPING_RELATION_DELEGATED
        infoblox_db.add_mapping_member(self.ctx.session, netview_id, member_id,
                                       relation)
        expected_rows.append(netview_id + ':' + member_id + ':' + relation)

        member_id = db_members[1]['member_id']
        relation = const.MAPPING_RELATION_DELEGATED
        infoblox_db.add_mapping_member(self.ctx.session, netview_id, member_id,
                                       relation)
        expected_rows.append(netview_id + ':' + member_id + ':' + relation)

        db_mapping_members = infoblox_db.get_mapping_members(self.ctx.session)
        actual_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            db_mapping_members, ':')
        self.assertEqual(expected_rows, actual_rows)

        # test mapping member update
        member_id = db_members[0]['member_id']
        relation = const.MAPPING_RELATION_GM_OWNED
        infoblox_db.update_mapping_member(self.ctx.session, netview_id,
                                          member_id, relation)
        expected_rows[0] = netview_id + ':' + member_id + ':' + relation

        db_mapping_members = infoblox_db.get_mapping_members(self.ctx.session)
        actual_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            db_mapping_members, ':')
        self.assertEqual(expected_rows, actual_rows)

        # test mapping member removals
        member_id = db_members[0]['member_id']
        infoblox_db.remove_mapping_member(self.ctx.session, netview_id,
                                          member_id)
        db_mapping_members = infoblox_db.get_mapping_members(
            self.ctx.session, member_id=member_id)
        self.assertEqual([], db_mapping_members)

    def test_grid_operations(self):
        # 'last_sync_time' operation type does not exist so it will add it
        last_sync_time = infoblox_db.get_last_sync_time(self.ctx.session)
        self.assertIsNone(last_sync_time)

        # 'last_sync_time' should exist now but its value should be None
        last_sync_time = infoblox_db.get_last_sync_time(self.ctx.session)
        self.assertIsNone(last_sync_time)

        # attempt to add 'last_sync_time' operation type should fail with
        # DBDuplicateEntry exception
        try:
            infoblox_db.add_operation_type(self.ctx.session,
                                           'last_sync_time',
                                           '')
            self.ctx.session.flush()
        except db_exc.DBDuplicateEntry as db_err:
            self.assertIsInstance(db_err, db_exc.DBDuplicateEntry)

        # test record_last_sync_time
        current_time = datetime.utcnow().replace(microsecond=0)
        infoblox_db.record_last_sync_time(self.ctx.session, current_time)
        last_sync_time = infoblox_db.get_last_sync_time(self.ctx.session)
        self.assertEqual(current_time, last_sync_time)

    def test_get_next_authority_member_for_ipam(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': 'GM',
                        'member_status': 'ON'},
                       {'member_id': 'm2',
                        'member_name': 'm2.com',
                        'member_ip': '10.10.1.2',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'ON'},
                       {'member_id': 'm3',
                        'member_name': 'm3.com',
                        'member_ip': '10.10.1.3',
                        'member_ipv6': None,
                        'member_type': 'CPM',
                        'member_status': 'ON'},
                       {'member_id': 'm4',
                        'member_name': 'm4.com',
                        'member_ip': '10.10.1.4',
                        'member_ipv6': None,
                        'member_type': 'REGULAR',
                        'member_status': 'ON'},
                       {'member_id': 'm5',
                        'member_name': 'm5.com',
                        'member_ip': '10.10.1.5',
                        'member_ipv6': None,
                        'member_type': 'CPM',
                        'member_status': 'OFF'},
                       {'member_id': 'm6',
                        'member_name': 'm6.com',
                        'member_ip': '10.10.1.6',
                        'member_ipv6': None,
                        'member_type': 'CPM',
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        # prepare network views
        netview_dict = {'default': 'm1',
                        'hs-view-1': 'm2',
                        'hs-view-2': 'm2',
                        'hs-view-3': 'm3'}
        self._create_network_views(netview_dict)

        # test for network view owning member (authority member)
        # the authority member must has the least number of network views
        authority_member = infoblox_db.get_next_authority_member_for_ipam(
            self.ctx.session, self.grid_id)
        # expect m6 since m6 owns the least number of network views
        expected = 'm6'
        self.assertEqual(expected, authority_member.member_id)

    def test_get_next_authority_member_for_dhcp_with_no_cpm(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': 'GM',
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        # prepare network views
        netview_dict = {'default': 'm1'}
        self._create_network_views(netview_dict)

        # test for network view owning member (authority member)
        # the authority member must has the least number of network views
        authority_member = infoblox_db.get_next_authority_member_for_dhcp(
            self.ctx.session, self.grid_id)
        self.assertIsNone(authority_member)

    def test_get_next_authority_member_for_dhcp_with_one_cpm(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': 'GM',
                        'member_status': 'ON'},
                       {'member_id': 'm2',
                        'member_name': 'm2.com',
                        'member_ip': '10.10.1.2',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        # prepare network views
        netview_dict = {'default': 'm1'}
        self._create_network_views(netview_dict)

        # test for network view owning member (authority member)
        # the authority member must has the least number of network views
        authority_member = infoblox_db.get_next_authority_member_for_dhcp(
            self.ctx.session, self.grid_id)
        expected_member_id = member_list[1]['member_id']
        self.assertEqual(expected_member_id, authority_member.member_id)

    def test_get_next_authority_member_for_dhcp_with_two_cpms(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': 'GM',
                        'member_status': 'ON'},
                       {'member_id': 'm2',
                        'member_name': 'm2.com',
                        'member_ip': '10.10.1.2',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': 'CPM',
                        'member_status': 'ON'},
                       {'member_id': 'm3',
                        'member_name': 'm3.com',
                        'member_ip': '10.10.1.3',
                        'member_ipv6': None,
                        'member_type': 'CPM',
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        # prepare network views
        netview_dict = {'default': 'm1'}
        self._create_network_views(netview_dict)

        # test for network view owning member (authority member)
        # the authority member must has the least number of network views
        authority_member = infoblox_db.get_next_authority_member_for_dhcp(
            self.ctx.session, self.grid_id)
        expected_member_ids = [m['member_id'] for m in member_list
                               if m['member_id'] == authority_member.member_id]
        self.assertEqual(expected_member_ids[0], authority_member.member_id)

    def test_get_next_dhcp_member(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': const.MEMBER_TYPE_GRID_MASTER,
                        'member_status': 'ON'},
                       {'member_id': 'm2',
                        'member_name': 'm2.com',
                        'member_ip': '10.10.1.2',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': const.MEMBER_TYPE_CP_MEMBER,
                        'member_status': 'ON'},
                       {'member_id': 'm3',
                        'member_name': 'm3.com',
                        'member_ip': '10.10.1.3',
                        'member_ipv6': None,
                        'member_type': const.MEMBER_TYPE_CP_MEMBER,
                        'member_status': 'ON'},
                       {'member_id': 'm4',
                        'member_name': 'm4.com',
                        'member_ip': '10.10.1.4',
                        'member_ipv6': None,
                        'member_type': const.MEMBER_TYPE_REGULAR_MEMBER,
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        db_members = infoblox_db.get_members(self.ctx.session,
                                             grid_id=self.grid_id)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)
        m2_member = utils.find_one_in_list('member_id', 'm2', db_members)
        m3_member = utils.find_one_in_list('member_id', 'm3', db_members)
        m4_member = utils.find_one_in_list('member_id', 'm4', db_members)

        # create network views
        netview_dict = {'default': gm_member.member_id,
                        'testview': m2_member.member_id}
        self._create_network_views(netview_dict)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        netview_default = utils.find_one_in_list('network_view',
                                                 'default',
                                                 db_network_views)
        netview_testview = utils.find_one_in_list('network_view',
                                                  'testview',
                                                  db_network_views)

        # add mapping members
        # - m1 (gm) is the authority member for 'default' view
        # - m2 is the authority member for 'testview' view as CPM
        infoblox_db.add_mapping_member(self.ctx.session,
                                       netview_default.id,
                                       gm_member.member_id,
                                       const.MAPPING_RELATION_GM_OWNED)
        infoblox_db.add_mapping_member(self.ctx.session,
                                       netview_testview.id,
                                       m2_member.member_id,
                                       const.MAPPING_RELATION_DELEGATED)

        # add service members
        # - m4 is a member that serves DHCP/DNS for a network under
        #   the non-delegated view, 'default'
        # - m2 is the delegated member to the network view, 'testview'
        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       m4_member.member_id,
                                       const.SERVICE_TYPE_DHCP)
        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       m4_member.member_id,
                                       const.SERVICE_TYPE_DNS)
        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       m2_member.member_id,
                                       const.SERVICE_TYPE_DHCP)
        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       m2_member.member_id,
                                       const.SERVICE_TYPE_DNS)

        dhcp_member = infoblox_db.get_next_dhcp_member(self.ctx.session,
                                                       self.grid_id)

        # only available dhcp member should be 'm3'
        self.assertEqual(m3_member.member_id, dhcp_member.member_id)

    def test_service_member(self):
        # prepare grid
        self._create_default_grid()

        # prepare grid members
        member_list = [{'member_id': 'm1',
                        'member_name': 'm1.com',
                        'member_ip': '10.10.1.1',
                        'member_ipv6': None,
                        'member_type': const.MEMBER_TYPE_GRID_MASTER,
                        'member_status': 'ON'},
                       {'member_id': 'm2',
                        'member_name': 'm2.com',
                        'member_ip': '10.10.1.2',
                        'member_ipv6': 'fd44:acb:5df6:1083::22',
                        'member_type': const.MEMBER_TYPE_CP_MEMBER,
                        'member_status': 'ON'}]
        self._create_members(member_list, self.grid_id)

        db_members = infoblox_db.get_members(self.ctx.session,
                                             grid_id=self.grid_id)
        gm_member = utils.find_one_in_list('member_type', 'GM', db_members)
        m2_member = utils.find_one_in_list('member_id', 'm2', db_members)

        # create network views
        netview_dict = {'default': gm_member.member_id}
        self._create_network_views(netview_dict)

        db_network_views = infoblox_db.get_network_views(self.ctx.session)
        netview_default = utils.find_one_in_list('network_view',
                                                 'default',
                                                 db_network_views)

        # test addition
        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       gm_member.member_id,
                                       const.SERVICE_TYPE_DHCP)

        infoblox_db.add_service_member(self.ctx.session,
                                       netview_default.id,
                                       m2_member.member_id,
                                       const.SERVICE_TYPE_DHCP)

        db_service_members = infoblox_db.get_service_members(
            self.ctx.session, netview_default.id)
        gm_dhcp_member = utils.find_one_in_list('member_id',
                                                gm_member.member_id,
                                                db_service_members)
        self.assertIsNotNone(gm_dhcp_member)
        m2_dhcp_member = utils.find_one_in_list('member_id',
                                                m2_member.member_id,
                                                db_service_members)
        self.assertIsNotNone(m2_dhcp_member)

        # test removal
        infoblox_db.remove_service_member(self.ctx.session, netview_default.id)
        db_service_members = infoblox_db.get_service_members(
            self.ctx.session, netview_default.id)
        gm_dhcp_member = utils.find_one_in_list('member_id',
                                                gm_member.member_id,
                                                db_service_members)
        self.assertIsNone(gm_dhcp_member)

        m2m_dhcp_member = utils.find_one_in_list('member_id',
                                                 m2_member.member_id,
                                                 db_service_members)
        self.assertIsNone(m2m_dhcp_member)

    def _create_instances(self, instances):
        for id, name in instances.items():
            infoblox_db.add_instance(self.ctx.session, id, name)

    def test_add_and_get_instance(self):
        instances = {'instance-id': 'instance-name'}
        self._create_instances(instances)
        instance = infoblox_db.get_instance(self.ctx.session, 'instance-id')
        self.assertEqual('instance-name', instance.instance_name)

    def test_get_instances(self):
        instances = {'instance-one': 'instance-name-1',
                     'instance-two': 'instance-name-2',
                     'instance-three': 'instance-name-3'}
        self._create_instances(instances)
        instances = infoblox_db.get_instances(
            self.ctx.session, ['instance-one', 'instance-three'])
        self.assertEqual(2, len(instances))

    def test_add_or_update_instance(self):
        instances = {'instance-id1': 'instance-name1'}
        self._create_instances(instances)
        new_instance_name = 'instance-name-updated'
        infoblox_db.add_or_update_instance(self.ctx.session,
                                           'instance-id1', new_instance_name)
        instance = infoblox_db.get_instance(self.ctx.session, 'instance-id1')
        self.assertEqual(new_instance_name, instance.instance_name)

        infoblox_db.add_or_update_instance(self.ctx.session,
                                           'instance-id2', 'instance-name2')
        instance = infoblox_db.get_instance(self.ctx.session, 'instance-id2')
        self.assertEqual('instance-name2', instance.instance_name)

    def _create_networks(self, networks):
        for id, name in networks.items():
            infoblox_db.add_network(self.ctx.session, id, name)

    def test_add_and_get_network(self):
        networks = {'network-id': 'network-name'}
        self._create_networks(networks)
        network = infoblox_db.get_network(self.ctx.session, 'network-id')
        self.assertEqual('network-name', network.network_name)

    def test_add_or_update_network(self):
        networks = {'network-id1': 'network-name1'}
        self._create_networks(networks)
        new_network_name = 'network-name-updated'
        infoblox_db.add_or_update_network(self.ctx.session,
                                          'network-id1', new_network_name)
        network = infoblox_db.get_network(self.ctx.session, 'network-id1')
        self.assertEqual(new_network_name, network.network_name)

        infoblox_db.add_or_update_network(self.ctx.session,
                                          'network-id2', 'network-name2')
        network = infoblox_db.get_network(self.ctx.session, 'network-id2')
        self.assertEqual('network-name2', network.network_name)
