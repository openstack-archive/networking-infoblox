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

import mock
from oslo_serialization import jsonutils

from neutron import context
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import member
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi

from networking_infoblox.tests import base


class GridMemberTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):

        super(GridMemberTestCase, self).setUp()
        self.ctx = context.get_admin_context()

        self.test_grid_config = grid.GridConfiguration(self.ctx)
        self.test_grid_config.gm_connector = mock.Mock()
        self.test_grid_config.grid_id = 100
        self.test_grid_config.grid_name = "Test Grid 1"
        self.test_grid_config.grid_master_host = '192.168.1.7'
        self.test_grid_config.grid_master_name = 'nios-7.2.0-master.com'
        self.test_grid_config.admin_user_name = 'admin'
        self.test_grid_config.admin_password = 'infoblox'
        self.test_grid_config.wapi_version = '2.2'

    def test_sync_grid(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        grids = dbi.get_grids(self.ctx.session)
        self.assertEqual(1, len(grids))
        self.assertEqual(self.test_grid_config.grid_id, grids[0]['grid_id'])
        self.assertEqual(self.test_grid_config.grid_name,
                         grids[0]['grid_name'])
        expected_grid_connection = {
            "wapi_version": self.test_grid_config.wapi_version,
            "ssl_verify": self.test_grid_config.ssl_verify,
            "http_pool_connections":
                self.test_grid_config.http_pool_connections,
            "http_pool_maxsize": self.test_grid_config.http_pool_maxsize,
            "http_request_timeout":
                self.test_grid_config.http_request_timeout,
            "admin_user": {"name": self.test_grid_config.admin_user_name,
                           "password": self.test_grid_config.admin_password}
        }
        actual_grid_connection = jsonutils.loads(grids[0]['grid_connection'])
        self.assertEqual(expected_grid_connection, actual_grid_connection)
        self.assertEqual('ON', grids[0]['grid_status'])

        # change active grid to "Test Grid 2"
        new_active_grid_config = grid.GridConfiguration(self.ctx)
        new_active_grid_config.gm_connector = mock.Mock()
        new_active_grid_config.grid_id = 200
        new_active_grid_config.grid_name = "Test Grid 2"
        new_active_grid_config.grid_master_host = '192.168.1.8'
        new_active_grid_config.admin_user_name = 'admin'
        new_active_grid_config.admin_password = 'infoblox'
        new_active_grid_config.wapi_version = '1.4.2'
        member_mgr = member.GridMemberManager(new_active_grid_config)
        member_mgr.sync_grid()

        grids = dbi.get_grids(self.ctx.session)
        self.assertEqual(2, len(grids))
        self.assertEqual(self.test_grid_config.grid_id, grids[0]['grid_id'])
        self.assertEqual('OFF', grids[0]['grid_status'])

        self.assertEqual(new_active_grid_config.grid_id, grids[1]['grid_id'])
        self.assertEqual(new_active_grid_config.grid_name,
                         grids[1]['grid_name'])
        expected_grid_connection = {
            "wapi_version": new_active_grid_config.wapi_version,
            "ssl_verify": new_active_grid_config.ssl_verify,
            "http_pool_connections":
                new_active_grid_config.http_pool_connections,
            "http_pool_maxsize": new_active_grid_config.http_pool_maxsize,
            "http_request_timeout":
                new_active_grid_config.http_request_timeout,
            "admin_user": {"name": new_active_grid_config.admin_user_name,
                           "password": new_active_grid_config.admin_password}
        }
        actual_grid_connection = jsonutils.loads(grids[1]['grid_connection'])
        self.assertEqual(expected_grid_connection, actual_grid_connection)
        self.assertEqual('ON', grids[1]['grid_status'])

    def test_sync_member_without_cloud_support(self):
        # wapi version less than 2.0 indicates no cloud support
        self.test_grid_config.wapi_version = '1.4.2'
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITHOUT_CLOUD)
        member_mgr._discover_members = mock.Mock()
        member_mgr._discover_members.return_value = member_json

        member_mgr._discover_member_licenses = mock.Mock()
        member_mgr._discover_member_licenses.return_value = None
        member_mgr.sync_members()

        members = dbi.get_members(self.ctx.session)
        self.assertEqual(len(member_json), len(members))
        for m in members:
            if self.test_grid_config.grid_master_host == m['member_ip']:
                self.assertEqual('GM', m['member_type'])
            else:
                self.assertEqual('REGULAR', m['member_type'])

    def test_sync_member_with_cloud_support_without_member_licenses(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITH_CLOUD)
        member_mgr._discover_members = mock.Mock()
        member_mgr._discover_members.return_value = member_json

        member_mgr._discover_member_licenses = mock.Mock()
        member_mgr._discover_member_licenses.return_value = None

        member_mgr.sync_members()

        members = dbi.get_members(self.ctx.session)
        self.assertEqual(len(member_json), len(members))
        for m in members:
            if self.test_grid_config.grid_master_host == m['member_ip']:
                self.assertEqual('GM', m['member_type'])
            else:
                self.assertEqual('REGULAR', m['member_type'])

    def test_sync_member_with_cloud_support_with_member_licenses(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITH_CLOUD)
        member_mgr._discover_members = mock.Mock()
        member_mgr._discover_members.return_value = member_json

        license_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBER_LICENSES)
        member_mgr._discover_member_licenses = mock.Mock()
        member_mgr._discover_member_licenses.return_value = license_json

        member_mgr.sync_members()

        # member_type is computed base on member licenses. To prove correctness
        # of member types, we need to first figure out which member has
        # 'CLOUD_API' license. A member with 'CLOUD_API' is CPM; otherwise
        # 'REGULAR'. Grid master member is 'GM'
        cloud_member_list = []
        cloud_lecensed_members = utils.find_in_list('type', ['CLOUD_API'],
                                                    license_json)
        member_hwids = utils.get_values_from_records('hwid',
                                                     cloud_lecensed_members)
        for m in member_json:
            member_id_arg = str(self.test_grid_config.grid_id) + m['host_name']
            member_id = utils.get_hash(member_id_arg)
            member_hwid = m['node_info'][0].get('hwid')
            if member_hwid in member_hwids:
                cloud_member_list.append(member_id)

        # now we know member licenses so get members in db
        members = dbi.get_members(self.ctx.session)
        self.assertEqual(len(member_json), len(members))
        # verify member types
        for m in members:
            if self.test_grid_config.grid_master_host == m['member_ip']:
                self.assertEqual('GM', m['member_type'])
            else:
                if m['member_id'] in cloud_member_list:
                    self.assertEqual('CPM', m['member_type'])
                else:
                    self.assertEqual('REGULAR', m['member_type'])
