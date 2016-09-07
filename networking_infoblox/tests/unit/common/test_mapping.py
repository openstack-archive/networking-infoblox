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
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import mapping
from networking_infoblox.neutron.common import member
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi

from networking_infoblox.tests import base


DELIMITER = '^'


class GridMappingTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):

        super(GridMappingTestCase, self).setUp()
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
        self.member_mgr = member.GridMemberManager(self.test_grid_config)

    def _create_members_with_cloud(self):
        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITH_CLOUD)
        license_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBER_LICENSES)

        self.member_mgr._discover_members = mock.Mock(return_value=member_json)
        self.member_mgr._discover_member_licenses = mock.Mock(
            return_value=license_json)

        self.member_mgr._discover_dns_settings = mock.Mock(return_value=[])
        self.member_mgr._discover_dhcp_settings = mock.Mock(return_value=[])

        self.member_mgr.sync()

    def _create_members_without_cloud(self):
        member_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_MEMBERS_WITHOUT_CLOUD)
        self.member_mgr._discover_members = mock.Mock()
        self.member_mgr._discover_members.return_value = member_json

        self.member_mgr._discover_member_licenses = mock.Mock()
        self.member_mgr._discover_member_licenses.return_value = None

        self.member_mgr.sync()

    def _validate_network_views(self, network_view_json):
        db_network_views = dbi.get_network_views(self.ctx.session)
        self.assertEqual(len(network_view_json), len(db_network_views))
        expected = [nv['name'] for nv in network_view_json]
        actual = utils.get_values_from_records('network_view',
                                               db_network_views)
        self.assertEqual(expected, actual)

    def _validate_mapping_conditions(self, network_view_json):
        db_network_views = dbi.get_network_views(self.ctx.session)
        db_mapping_conditions = dbi.get_mapping_conditions(self.ctx.session)

        expected_conditions = dict((nv['name'], nv['extattrs'])
                                   for nv in network_view_json
                                   if nv['extattrs'])
        expected_condition_rows = []
        for netview in expected_conditions:
            netview_row = utils.find_one_in_list('network_view', netview,
                                                 db_network_views)
            netview_id = netview_row.id
            for condition_name in expected_conditions[netview]:
                if 'Mapping' not in condition_name:
                    continue
                values = expected_conditions[netview][condition_name]['value']
                if not isinstance(values, list):
                    expected_condition_rows.append(netview_id + DELIMITER +
                                                   condition_name + DELIMITER +
                                                   values)
                    continue
                for value in values:
                    expected_condition_rows.append(netview_id + DELIMITER +
                                                   condition_name + DELIMITER +
                                                   value)

        actual_condition_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'neutron_object_name', 'neutron_object_value'],
            db_mapping_conditions)
        self.assertEqual(set(expected_condition_rows),
                         set(actual_condition_rows))

    def _validate_member_mapping(self, network_view_json, network_json):
        db_members = dbi.get_members(self.ctx.session,
                                     grid_id=self.test_grid_config.grid_id)
        db_network_views = dbi.get_network_views(self.ctx.session)
        db_mapping_members = dbi.get_mapping_members(self.ctx.session)
        db_service_members = dbi.get_service_members(self.ctx.session)

        gm_row = utils.find_one_in_list('member_type',
                                        const.MEMBER_TYPE_GRID_MASTER,
                                        db_members)
        gm_member_id = gm_row.member_id

        dedicated_delegation_members = dict()
        for netview in network_view_json:
            netview_name = netview['name']
            if (netview.get('cloud_info') and
                    netview.get('cloud_info').get('delegated_member')):
                delegated_member = utils.find_one_in_list(
                    'member_name',
                    netview['cloud_info']['delegated_member']['name'],
                    db_members)
                dedicated_delegation_members[netview_name] = (
                    delegated_member.member_id)

        expected_mapping_members = []
        expected_service_members = []

        # get delegated authority members from network views
        for netview in dedicated_delegation_members:
            netview_row = utils.find_one_in_list('network_view', netview,
                                                 db_network_views)
            netview_id = netview_row.id
            authority_member = dedicated_delegation_members[netview]
            mapping_relation = const.MAPPING_RELATION_DELEGATED
            mapping_row_info = (netview_id + DELIMITER + authority_member +
                                DELIMITER + mapping_relation)
            expected_mapping_members.append(mapping_row_info)

        # get authority members from networks
        for network in network_json:
            netview = network['network_view']
            netview_row = utils.find_one_in_list('network_view', netview,
                                                 db_network_views)
            netview_id = netview_row.id

            mapping_relation = const.MAPPING_RELATION_GM_OWNED
            authority_member = gm_member_id
            if netview in dedicated_delegation_members:
                authority_member = dedicated_delegation_members[netview]
                mapping_relation = const.MAPPING_RELATION_DELEGATED
            elif (network.get('cloud_info') and
                    network['cloud_info'].get('delegated_member')):
                delegated_member = utils.find_one_in_list(
                    'member_name',
                    network['cloud_info']['delegated_member']['name'],
                    db_members)
                authority_member = delegated_member.member_id
                mapping_relation = const.MAPPING_RELATION_DELEGATED

            mapping_row_info = (netview_id + DELIMITER + authority_member +
                                DELIMITER + mapping_relation)
            if mapping_row_info not in expected_mapping_members:
                expected_mapping_members.append(mapping_row_info)

            if network.get('members'):
                for m in network['members']:
                    if m['_struct'] == 'dhcpmember':
                        dhcp_member = utils.find_one_in_list(
                            'member_name', m['name'], db_members)
                        mapping_row_info = (netview_id + DELIMITER +
                                            dhcp_member.member_id + DELIMITER +
                                            const.SERVICE_TYPE_DHCP)
                        if mapping_row_info not in expected_service_members:
                            expected_service_members.append(mapping_row_info)

            if network.get('options'):
                dns_membe_ips = []
                for option in network['options']:
                    if option.get('name') == 'domain-name-servers':
                        option_values = option.get('value')
                        if option_values:
                            dns_membe_ips = option_values.split(',')
                            break
                for membe_ip in dns_membe_ips:
                    dns_member = utils.find_one_in_list(
                        'member_ip', membe_ip, db_members)
                    mapping_row_info = (netview_id + DELIMITER +
                                        dns_member.member_id + DELIMITER +
                                        const.SERVICE_TYPE_DNS)
                    if mapping_row_info not in expected_service_members:
                        expected_service_members.append(mapping_row_info)

        actual_mapping_members = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            db_mapping_members)
        self.assertEqual(set(expected_mapping_members),
                         set(actual_mapping_members))

        actual_service_members = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'service'],
            db_service_members)
        self.assertEqual(set(expected_service_members),
                         set(actual_service_members))

    def test_sync_for_cloud(self):
        self._create_members_with_cloud()

        mapping_mgr = mapping.GridMappingManager(self.test_grid_config)
        mapping_mgr._sync_nios_for_network_view = mock.Mock()

        network_view_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_NETWORKVIEW_WITH_CLOUD)
        mapping_mgr._discover_network_views = mock.Mock()
        mapping_mgr._discover_network_views.return_value = network_view_json

        network_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_NETWORK_WITH_CLOUD)
        mapping_mgr._discover_networks = mock.Mock()
        mapping_mgr._discover_networks.return_value = network_json

        dnsview_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_DNS_VIEW)
        mapping_mgr._discover_dns_views = mock.Mock()
        mapping_mgr._discover_dns_views.return_value = dnsview_json

        mapping_mgr.sync()

        # validate network views, mapping conditions, mapping members
        self._validate_network_views(network_view_json)
        self._validate_mapping_conditions(network_view_json)
        self._validate_member_mapping(network_view_json, network_json)

    def test_sync_for_without_cloud(self):
        self._create_members_with_cloud()

        mapping_mgr = mapping.GridMappingManager(self.test_grid_config)
        mapping_mgr._sync_nios_for_network_view = mock.Mock()

        network_view_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_NETWORKVIEW_WITHOUT_CLOUD)
        mapping_mgr._discover_network_views = mock.Mock()
        mapping_mgr._discover_network_views.return_value = network_view_json

        network_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_NETWORK_WITHOUT_CLOUD)
        mapping_mgr._discover_networks = mock.Mock()
        mapping_mgr._discover_networks.return_value = network_json

        dnsview_json = self.connector_fixture.get_object(
            base.FixtureResourceMap.FAKE_DNS_VIEW)
        mapping_mgr._discover_dns_views = mock.Mock()
        mapping_mgr._discover_dns_views.return_value = dnsview_json

        mapping_mgr.sync()

        # validate network views, mapping conditions, mapping members
        self._validate_network_views(network_view_json)
        self._validate_mapping_conditions(network_view_json)
        self._validate_member_mapping(network_view_json, network_json)
