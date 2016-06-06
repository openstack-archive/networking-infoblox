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

from neutron import context
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import member
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi

from networking_infoblox.tests import base
from networking_infoblox.tests.unit import grid_sync_stub


class GridTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(GridTestCase, self).setUp()
        self.ctx = context.get_admin_context()

        self.test_grid_config = grid.GridConfiguration(self.ctx)
        self.test_grid_config.gm_connector = mock.Mock()
        self.test_grid_config.grid_id = 100
        self.test_grid_config.grid_name = "Test Grid 1"
        self.test_grid_config.grid_master_host = '192.168.1.7'
        self.test_grid_config.grid_master_name = 'nios-7.2.0-master.com'
        self.test_grid_config.admin_username = 'admin'
        self.test_grid_config.admin_password = 'infoblox'
        self.test_grid_config.wapi_version = '2.2'

    def _prepare_grid_member(self):
        # create grid
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        # create members
        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITH_CLOUD)
        member_mgr._discover_members = mock.Mock(return_value=member_json)
        member_mgr._discover_member_licenses = mock.Mock(return_value=None)
        member_mgr._discover_dns_settings = mock.Mock(return_value=[])
        member_mgr._discover_dhcp_settings = mock.Mock(return_value=[])

        member_mgr.sync_members()

    def test_grid_configuration_without_grid_member(self):
        # grid member sync is required; thus it throws an exception when
        # grid member discovery is not performed
        self.assertRaises(exc.InfobloxCannotFindMember,
                          self.test_grid_config.sync)

    def test_grid_configuration_with_grid_member(self):
        # prepare grid members.
        self._prepare_grid_member()

        # check if GM exists
        db_members = dbi.get_members(self.ctx.session,
                                     grid_id=self.test_grid_config.grid_id,
                                     member_type='GM')
        self.assertEqual('GM', db_members[0]['member_type'])

        # get grid config from GM
        config_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_GRID_MASTER_GRID_CONFIGURATION)
        self.test_grid_config._discover_config = mock.Mock()
        self.test_grid_config._discover_config.return_value = config_json
        self.test_grid_config.sync()

        # verify if grid config object fields are set correctly
        expected = utils.get_ea_value('Default Network View Scope',
                                      config_json)
        self.assertEqual(expected,
                         self.test_grid_config.default_network_view_scope)
        expected = utils.get_ea_value('Default Network View', config_json)
        self.assertEqual(expected,
                         self.test_grid_config.default_network_view)
        expected = utils.get_ea_value('IP Allocation Strategy', config_json)
        self.assertEqual(expected,
                         self.test_grid_config.ip_allocation_strategy)
        expected = utils.get_ea_value('Default Domain Name Pattern',
                                      config_json)
        self.assertEqual(expected,
                         self.test_grid_config.default_domain_name_pattern)
        expected = utils.get_ea_value('Default Host Name Pattern',
                                      config_json)
        self.assertEqual(expected,
                         self.test_grid_config.default_host_name_pattern)
        expected = utils.get_ea_value('DNS Record Binding Types',
                                      config_json)
        self.assertEqual(expected,
                         self.test_grid_config.dns_record_binding_types)

    def test_grid_sync_frequency_check(self):
        # prepare grid manager for sync
        stub = grid_sync_stub.GridSyncStub(self.ctx, self.connector_fixture)
        stub.prepare_grid_manager(wapi_version='1.8')
        grid_mgr = stub.get_grid_manager()
        grid_mgr._report_sync_time = mock.Mock()
        grid_mgr.mapping._sync_nios_for_network_view = mock.Mock()

        # test for no sync
        grid_mgr.grid_config.grid_sync_support = False
        grid_mgr.sync()
        assert not grid_mgr.member._discover_members.called
        assert not grid_mgr.grid_config._discover_config.called
        assert not grid_mgr.mapping._discover_network_views.called
        assert not grid_mgr.mapping._discover_networks.called
        last_sync_time = dbi.get_last_sync_time(self.ctx.session)
        self.assertIsNone(last_sync_time)

        # test for the first sync; expects sync
        grid_mgr.grid_config.grid_sync_support = True
        grid_mgr.sync()
        assert grid_mgr.member._discover_members.called_once
        assert grid_mgr.grid_config._discover_config.called_once
        assert grid_mgr.mapping._discover_network_views.called_once
        assert grid_mgr.mapping._discover_networks.called_once
        sync_time_from_second_sync = dbi.get_last_sync_time(self.ctx.session)
        self.assertEqual(sync_time_from_second_sync, grid_mgr.last_sync_time)

        # test for the second sync; expects no sync due to min wait time
        grid_mgr.grid_config.grid_sync_support = True
        grid_mgr.grid_config.grid_sync_minimum_wait_time = 10
        grid_mgr.sync()
        assert grid_mgr.member._discover_members.called_once
        assert grid_mgr.grid_config._discover_config.called_once
        assert grid_mgr.mapping._discover_network_views.called_once
        assert grid_mgr.mapping._discover_networks.called_once
        # should be the same as last_sync_time from the first sync
        # to prove that dicovery methods are not called in this test case.
        self.assertEqual(sync_time_from_second_sync, grid_mgr.last_sync_time)

        # test for the third sync; expects sync
        grid_mgr.grid_config.grid_sync_support = True
        grid_mgr.grid_config.grid_sync_minimum_wait_time = 0
        grid_mgr.sync()
        assert grid_mgr.member._discover_members.called_once
        assert grid_mgr.grid_config._discover_config.called_once
        assert grid_mgr.mapping._discover_network_views.called_once
        assert grid_mgr.mapping._discover_networks.called_once
        last_sync_time = dbi.get_last_sync_time(self.ctx.session)
        self.assertEqual(last_sync_time, grid_mgr.last_sync_time)

    def _mock_connector(self, get_object=None, create_object=None,
                        delete_object=None):
        connector = mock.Mock()
        connector.get_object.return_value = get_object
        connector.create_object.return_value = create_object
        connector.delete_object.return_value = delete_object
        return connector

    def test_grid_sync_report_sync_time(self):
        # prepare grid manager for sync
        stub = grid_sync_stub.GridSyncStub(self.ctx, self.connector_fixture)
        stub.prepare_grid_manager(wapi_version='1.8')
        grid_mgr = stub.get_grid_manager()
        grid_mgr.mapping._sync_nios_for_network_view = mock.Mock()

        eas = {'Some EA': {'value': 'False'},
               'Zero EA': {'value': '0'}}
        member_mock = {'_ref': ('member/Li5pcHY0X2FkZHJlc3MkMTky'
                                'LjE2OC4xLjEwLzE:192.168.1.10/my_view'),
                       'ipv4_address': '192.168.1.10',
                       'host_name': 'gm',
                       'extattrs': eas}
        connector = self._mock_connector(get_object=[member_mock])
        connector.host = '192.168.1.10'
        grid_mgr.grid_config.gm_connector = connector

        # sync
        grid_mgr.grid_config.grid_sync_support = True
        grid_mgr.grid_config.grid_sync_minimum_wait_time = 0
        grid_mgr.grid_config.report_grid_sync_time = True
        grid_mgr.sync()

        member_ea = member_mock['extattrs'].to_dict()
        sync_info = member_ea[const.EA_LAST_GRID_SYNC_TIME]['value']
        assert isinstance(sync_info, list)
        assert grid_mgr.hostname in sync_info[0]

    def test_grid_sync_report_sync_time_multi_nodes(self):
        # prepare grid manager for sync
        stub = grid_sync_stub.GridSyncStub(self.ctx, self.connector_fixture)
        stub.prepare_grid_manager(wapi_version='1.8')
        grid_mgr = stub.get_grid_manager()
        grid_mgr.mapping._sync_nios_for_network_view = mock.Mock()

        # create a new hostname to report another sync time
        eas = {'Some EA': {'value': 'False'},
               'Zero EA': {'value': '0'},
               'Last Grid Sync Time':
                   {'value': ['controller-1 => 2016-01-28 19:44:56']}}
        member_mock = {'_ref': ('member/Li5pcHY0X2FkZHJlc3MkMTky'
                                'LjE2OC4xLjEwLzE:192.168.1.10/my_view'),
                       'ipv4_address': '192.168.1.10',
                       'host_name': 'gm',
                       'extattrs': eas}
        connector = self._mock_connector(get_object=[member_mock])
        connector.host = '192.168.1.10'
        grid_mgr.grid_config.gm_connector = connector
        grid_mgr.hostname = 'controller-2'

        grid_mgr.grid_config.grid_sync_support = True
        grid_mgr.grid_config.grid_sync_minimum_wait_time = 0
        grid_mgr.grid_config.report_grid_sync_time = True
        grid_mgr.sync()

        member_ea = member_mock['extattrs'].to_dict()
        sync_info = member_ea[const.EA_LAST_GRID_SYNC_TIME]['value']
        assert isinstance(sync_info, list) and len(sync_info) == 2
        assert grid_mgr.hostname in sync_info[1]

    def test__set_default_values(self):
        # validate that default values are set as member properties
        for prop, key in self.test_grid_config.property_to_ea_mapping.items():
            self.assertEqual(const.GRID_CONFIG_DEFAULTS[key],
                             getattr(self.test_grid_config, prop))
