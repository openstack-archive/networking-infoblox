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
        self.test_grid_config.wapi_version = '2.3'

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

    def _mock_member_mgr(self, member_mgr, discover_members=None,
                         discover_member_licenses=None):
        member_mgr._discover_members = mock.Mock(return_value=discover_members)
        member_mgr._discover_member_licenses = mock.Mock(
            return_value=discover_member_licenses)

        member_mgr._discover_dns_settings = mock.Mock(return_value=[])
        member_mgr._discover_dhcp_settings = mock.Mock(return_value=[])
        return member_mgr

    def test_sync_member_without_cloud_support(self):
        # wapi version less than 2.0 indicates no cloud support
        self.test_grid_config.wapi_version = '1.4.2'
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr.sync_grid()

        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITHOUT_CLOUD)
        self._mock_member_mgr(member_mgr, discover_members=member_json)

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
        self._mock_member_mgr(member_mgr, discover_members=member_json)

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
        license_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBER_LICENSES)
        self._mock_member_mgr(member_mgr, discover_members=member_json,
                              discover_member_licenses=license_json)

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

    def test__discover_dns_settings(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_dns = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBER_DNS)

        return_fields = ['host_name', 'use_mgmt_port', 'use_mgmt_ipv6_port',
                         'use_lan_port', 'use_lan_ipv6_port', 'use_lan2_port',
                         'use_lan2_ipv6_port', 'additional_ip_list']

        get_mock = mock.Mock(return_value=member_dns)
        member_mgr._connector.get_object = get_mock

        dns_settings = member_mgr._discover_dns_settings()
        get_mock.assert_called_once_with('member:dns',
                                         return_fields=return_fields)
        self.assertEqual(1, len(dns_settings))
        self.assertTrue('nios-7.2.0-master.com' in dns_settings)

    def test__discover_dns_settings_old_wapi(self):
        # make sure wapi calls are not done on wapi older then 2.3
        self.test_grid_config.wapi_version = '2.2.1'
        member_mgr = member.GridMemberManager(self.test_grid_config)
        get_mock = mock.Mock()
        member_mgr._connector.get_object = get_mock

        dns_settings = member_mgr._discover_dns_settings()
        self.assertEqual({}, dns_settings)
        get_mock.assert_not_called()

    def test__discover_dhcp_settings(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_dhcp = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBER_DHCP)

        return_fields = ['host_name', 'enable_dhcp']

        get_mock = mock.Mock(return_value=member_dhcp)
        member_mgr._connector.get_object = get_mock

        dhcp_settings = member_mgr._discover_dhcp_settings()
        get_mock.assert_called_once_with('member:dhcpproperties',
                                         return_fields=return_fields)
        self.assertEqual(1, len(dhcp_settings))
        self.assertTrue('nios-7.2.0-master.com' in dhcp_settings)

    def test__discover_dhcp_settings_old_wapi(self):
        # make sure wapi calls are not done on wapi older then 2.2.1
        self.test_grid_config.wapi_version = '2.2'
        member_mgr = member.GridMemberManager(self.test_grid_config)
        get_mock = mock.Mock()
        member_mgr._connector.get_object = get_mock

        dhcp_settings = member_mgr._discover_dhcp_settings()
        self.assertEqual({}, dhcp_settings)
        get_mock.assert_not_called()

    def test__get_dhcp_ips_lan1(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_dict = {'host_name': 'nios-7.2.0-master.com',
                       'vip_setting': {'address': '172.22.0.10'},
                       'ipv6_setting': {'virtual_ip': '2001::12'}}
        dhcp_settings = {'nios-7.2.0-master.com':
                         {'host_name': 'nios-7.2.0-master.com',
                          'enabled': True}}
        # should return lan1 settings
        ip, ipv6 = member_mgr._get_dhcp_ips(member_dict, dhcp_settings)
        self.assertEqual('172.22.0.10', ip)
        self.assertEqual('2001::12', ipv6)

    def test__get_dhcp_ips_lan2(self):
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_dict = {'host_name': 'nios-7.2.0-master.com',
                       'vip_setting': {'address': '172.22.0.10'},
                       'ipv6_setting': {'virtual_ip': '2001::12'},
                       'lan2_port_setting':
                           {'network_setting': {'address': '172.25.0.10'},
                            'v6_network_setting': {'virtual_ip': '2022::25'}}}
        dhcp_settings = {'nios-7.2.0-master.com':
                         {'host_name': 'nios-7.2.0-master.com',
                          'enabled': False}}
        # should return lan2 settings
        ip, ipv6 = member_mgr._get_dhcp_ips(member_dict, dhcp_settings)
        self.assertEqual('172.25.0.10', ip)
        self.assertEqual('2022::25', ipv6)

    def _test__get_dns_ips(self, use_lan2_ipv6_port=False,
                           use_lan2_port=False, use_lan_ipv6_port=False,
                           use_lan_port=False, use_mgmt_ipv6_port=False,
                           use_mgmt_port=False, additional_ips=None):
        if additional_ips is None:
            additional_ips = []
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_dict = {'host_name': 'nios-7.2.0-master.com',
                       'vip_setting': {'address': '172.22.0.10'},
                       'ipv6_setting': {'virtual_ip': '2001::12'},
                       'node_info': [
                           {'v6_mgmt_network_setting': {
                               'virtual_ip': '2050::55'},
                            'mgmt_network_setting': {
                                'address': '192.168.1.85'}}],
                       'lan2_port_setting':
                           {'network_setting': {'address': '172.25.0.10'},
                            'v6_network_setting': {'virtual_ip': '2022::25'}}}
        dns_settings = {'nios-7.2.0-master.com':
                        {'host_name': 'nios-7.2.0-master.com',
                         "additional_ip_list": additional_ips,
                         "use_lan2_ipv6_port": use_lan2_ipv6_port,
                         "use_lan2_port": use_lan2_port,
                         "use_lan_ipv6_port": use_lan_ipv6_port,
                         "use_lan_port": use_lan_port,
                         "use_mgmt_ipv6_port": use_mgmt_ipv6_port,
                         "use_mgmt_port": use_mgmt_port}}
        return member_mgr._get_dns_ips(member_dict, dns_settings)

    def test__get_dns_ips_lan1(self):
        ip, ipv6 = self._test__get_dns_ips(use_lan_port=True,
                                           use_lan_ipv6_port=True)
        self.assertEqual('172.22.0.10', ip)
        self.assertEqual('2001::12', ipv6)

    def test__get_dns_ips_lan2(self):
        ip, ipv6 = self._test__get_dns_ips(use_lan2_port=True,
                                           use_lan2_ipv6_port=True)
        self.assertEqual('172.25.0.10', ip)
        self.assertEqual('2022::25', ipv6)

    def test__get_dns_ips_mgmt(self):
        ip, ipv6 = self._test__get_dns_ips(use_mgmt_port=True,
                                           use_mgmt_ipv6_port=True)
        self.assertEqual('192.168.1.85', ip)
        self.assertEqual('2050::55', ipv6)

    def test__get_dns_ips_additional_ips(self):
        additional_ips = ['145.22.0.15', '2012::125']
        ip, ipv6 = self._test__get_dns_ips(additional_ips=additional_ips)
        self.assertEqual('145.22.0.15', ip)
        self.assertEqual('2012::125', ipv6)

    def test__get_dns_ips_fallback_to_lan1(self):
        ip, ipv6 = self._test__get_dns_ips()
        self.assertEqual('172.22.0.10', ip)
        self.assertEqual('2001::12', ipv6)

    def _test_discover_members(self, wapi_version, return_fields):
        self.test_grid_config.wapi_version = wapi_version
        member_mgr = member.GridMemberManager(self.test_grid_config)
        member_mgr._connector = mock.Mock()

        member_mgr._discover_members()

        member_mgr._connector.get_object.assert_called_with(
            'member', return_fields=return_fields)

    def test__discover_members_all_fields(self):
        wapi_version = '2.2'
        return_fields = ['node_info', 'host_name', 'vip_setting', 'extattrs',
                         'ipv6_setting', 'lan2_port_setting',
                         'mgmt_port_setting']
        self._test_discover_members(wapi_version, return_fields)

    def test__discover_members_not_all_fields(self):
        wapi_version = '2.1'
        return_fields = ['node_info', 'host_name', 'vip_setting', 'extattrs']
        self._test_discover_members(wapi_version, return_fields)
