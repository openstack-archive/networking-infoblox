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

import eventlet
eventlet.monkey_patch()

import mock

from neutron import context
from neutron import manager
from neutron.tests.unit import testlib_api

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context as ib_context
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi

from networking_infoblox.tests import base
from networking_infoblox.tests.unit import grid_sync_stub
from networking_infoblox.tests.unit import neutron_plugin_stub


class InfobloxContextTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(InfobloxContextTestCase, self).setUp()
        self.ctx = context.get_admin_context()

        self.setup_coreplugin(neutron_plugin_stub.DB_PLUGIN_KLASS)
        self.plugin = manager.NeutronManager.get_plugin()

        self.plugin_stub = neutron_plugin_stub.NeutronPluginStub(self.ctx,
                                                                 self.plugin)

        self.grid_stub = grid_sync_stub.GridSyncStub(self.ctx,
                                                     self.connector_fixture)
        self.grid_stub.prepare_grid_manager(wapi_version='2.2')
        self.grid_mgr = self.grid_stub.get_grid_manager()
        self.grid_mgr._report_sync_time = mock.Mock()
        self.grid_mgr.mapping._sync_nios_for_network_view = mock.Mock()
        self.grid_mgr.sync()

        self.grid_id = self.grid_mgr.grid_config.grid_id
        self.grid_config = self.grid_mgr.grid_config

    def test_network_view_mapping_conditions_with_single_scope(self):
        user_id = 'test user'
        tenant_id = 'test-tenant'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr tat is not used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '10.0.0.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        # make sure that no subnet cidr is used in mapping conditions
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=subnet_cidr)
        self.assertEqual([], db_conditions)

        # check default network view when no mapping condition matches
        self.assertEqual('Single',
                         self.grid_config.default_network_view_scope)
        self.assertEqual('default', self.grid_config.default_network_view)

        # test default mapping as 'Single'
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.connector = mock.Mock()
        ib_cxt.ibom = mock.Mock()
        ib_cxt.ip_allocator = mock.Mock()

        # verify that 'default' view is used
        db_netviews = dbi.get_network_views(self.ctx.session,
                                            grid_id=self.grid_id)
        netview_row = utils.find_one_in_list('network_view', 'default',
                                             db_netviews)
        expected_netview_id = netview_row.id

        db_grid_members = dbi.get_members(self.ctx.session,
                                          grid_id=self.grid_id)
        member_row = utils.find_one_in_list('member_type', 'GM',
                                            db_grid_members)
        expected_member_name = member_row.member_name

        self.assertEqual(expected_netview_id,
                         ib_cxt.mapping.network_view_id)
        self.assertEqual('default',
                         ib_cxt.mapping.network_view)
        self.assertEqual(expected_member_name,
                         ib_cxt.mapping.authority_member.member_name)

    def test_network_view_mapping_conditions_with_tenant_scope(self):
        user_id = 'test user'
        tenant_id = 'test-tenant-id'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr tat is not used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '10.0.0.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        # make sure that no subnet cidr is used in mapping conditions
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=subnet_cidr)
        self.assertEqual([], db_conditions)

        # set default network view scope to 'Tenant'
        self.grid_config.default_network_view_scope = (
            const.NETWORK_VIEW_SCOPE_TENANT)

        # test default mapping as 'Tenant'
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.connector = mock.Mock()
        ib_cxt.ibom = mock.Mock()
        ib_cxt.ip_allocator = mock.Mock()

        # validate the mapping network view
        expected_netview = utils.generate_network_view_name(tenant_id)
        self.assertIsNone(ib_cxt.mapping.network_view_id)
        self.assertEqual(expected_netview, ib_cxt.mapping.network_view)
        self.assertEqual(None, ib_cxt.mapping.authority_member)

    def test_network_view_mapping_conditions_with_tenant_id_condition(self):
        user_id = 'test user'
        tenant_id = '80afaaba012acb9c12888128d5123a09'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr tat is not used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '10.0.0.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        # make sure that no subnet cidr is used in mapping conditions
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=subnet_cidr)
        self.assertEqual([], db_conditions)

        # make sure that tenant id is used in mapping condition once
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=tenant_id)
        self.assertEqual(1, len(db_conditions))

        # test mapping where tenant id mapping is found
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.connector = mock.Mock()
        ib_cxt.ibom = mock.Mock()
        ib_cxt.ip_allocator = mock.Mock()

        # validate the mapping network view
        expected_netview_id = db_conditions[0].network_view_id
        db_netviews = dbi.get_network_views(self.ctx.session,
                                            grid_id=self.grid_id)
        netview_row = utils.find_one_in_list('id', expected_netview_id,
                                             db_netviews)
        expected_netview = netview_row.network_view

        db_mapping_members = dbi.get_mapping_members(self.ctx.session,
                                                     expected_netview_id,
                                                     grid_id=self.grid_id)
        expected_member_id = db_mapping_members[0].member_id

        self.assertEqual(expected_netview_id,
                         ib_cxt.mapping.network_view_id)
        self.assertEqual(expected_netview,
                         ib_cxt.mapping.network_view)
        self.assertEqual(expected_member_id,
                         ib_cxt.mapping.authority_member.member_id)

    def test_network_view_mapping_conditions_with_subnet_cidr_condition(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '12.12.2.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        # make sure that mapping condition exists and prepare expectations
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=subnet_cidr)
        self.assertEqual(1, len(db_conditions))
        expected_network_view_id = db_conditions[0].network_view_id

        db_network_views = dbi.get_network_views(self.ctx.session,
                                                 grid_id=self.grid_id)
        expected_netview_row = utils.find_one_in_list(
            'id', expected_network_view_id, db_network_views)
        expected_authority_member_id = expected_netview_row.authority_member_id
        expected_network_view = expected_netview_row.network_view

        # prepare network view mapping to neutron network and subnet
        dbi.associate_network_view(
            self.ctx.session, expected_network_view_id, network['id'],
            subnet['id'])

        # test mapping where both tenant id and tenant cidr match
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.connector = mock.Mock()
        ib_cxt.ibom = mock.Mock()
        ib_cxt.ip_allocator = mock.Mock()

        # validate mapping
        self.assertEqual(expected_network_view_id,
                         ib_cxt.mapping.network_view_id)
        self.assertEqual(expected_network_view,
                         ib_cxt.mapping.network_view)
        self.assertEqual(expected_authority_member_id,
                         ib_cxt.mapping.authority_member.member_id)

    @mock.patch.object(dbi, 'add_network_view')
    @mock.patch.object(dbi, 'get_next_authority_member_for_ipam')
    def test_reserve_authority_member_without_dhcp_support(
            self, dbi_next_authority_mock, dbi_network_view_mock):
        user_id = 'test user'
        self.grid_config.dhcp_support = False
        self.grid_config.dns_view = 'test-view'

        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id', 'member_type': 'GM',
             'member_ip': '11.11.1.10', 'member_ipv6': None,
             'member_dns_ip': '12.11.1.11', 'member_dns_ipv6': None,
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_wapi': '11.11.1.10'})
        dbi_next_authority_mock.return_value = test_authority_member

        test_network_view = utils.json_to_obj(
            'NetworkView',
            {'id': 'test-id', 'network_view': 'test-view', 'shared': False})
        dbi_network_view_mock.return_value = test_network_view

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, None, None,
                                            self.grid_config, self.plugin)
        ib_cxt.mapping.network_view = test_network_view.network_view

        ib_cxt.reserve_authority_member()

        self.assertEqual(test_network_view.network_view,
                         ib_cxt.mapping.network_view)
        self.assertEqual(test_authority_member.member_id,
                         ib_cxt.mapping.authority_member.member_id)

    @mock.patch.object(dbi, 'add_network_view')
    @mock.patch.object(dbi, 'get_next_authority_member_for_dhcp')
    def test_reserve_authority_member_with_dhcp_support(
            self, dbi_next_authority_mock, dbi_network_view_mock):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.2.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True

        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id', 'member_type': 'CPM',
             'member_ip': '11.11.1.11', 'member_ipv6': None,
             'member_dns_ip': '12.11.1.11', 'member_dns_ipv6': None,
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        dbi_next_authority_mock.return_value = test_authority_member

        test_network_view = utils.json_to_obj(
            'NetworkView',
            {'id': 'ZG5zLm5ldHdvcmtfdmlldyQ1', 'network_view': 'hs-view-1',
             'shared': False})
        dbi_network_view_mock.return_value = test_network_view

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.mapping.network_view = test_network_view.network_view
        ib_cxt.reserve_authority_member()

        self.assertEqual(test_network_view.network_view,
                         ib_cxt.mapping.network_view)
        self.assertEqual(test_authority_member.member_id,
                         ib_cxt.mapping.authority_member.member_id)

    def _test_reserve_service_members_without_ib_network_for_cpm_auth(
            self, test_authority_member, dns_support, expected_dns_members):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.2.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True
        self.grid_config.dns_support = dns_support

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.mapping.authority_member = test_authority_member
        ib_cxt._register_services = mock.Mock()

        ib_cxt.reserve_service_members()

        self.assertEqual([test_authority_member], ib_cxt.mapping.dhcp_members)
        self.assertEqual(expected_dns_members, ib_cxt.mapping.dns_members)

    def test_reserve_service_members_without_ib_network_for_cpm_authortity(
            self):
        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id', 'member_type': 'CPM',
             'member_ip': '11.11.1.11', 'member_ipv6': None,
             'member_dns_ip': '12.11.1.11', 'member_dns_ipv6': None,
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        self._test_reserve_service_members_without_ib_network_for_cpm_auth(
            test_authority_member,
            dns_support=True, expected_dns_members=[test_authority_member])
        self._test_reserve_service_members_without_ib_network_for_cpm_auth(
            test_authority_member,
            dns_support=False, expected_dns_members=[])

    @mock.patch.object(dbi, 'get_service_members')
    def _test_reserve_service_members_without_ib_network_for_gm_auth(
            self, test_authority_member, dns_support, expected_dns_members,
            dbi_service_member_mock):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True
        self.grid_config.dns_support = dns_support

        dbi_service_member_mock.return_value = []

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.mapping.authority_member = test_authority_member
        ib_cxt.grid_config.use_grid_master_for_dhcp = True
        ib_cxt._register_services = mock.Mock()

        ib_cxt.reserve_service_members()

        self.assertEqual(test_authority_member.member_id,
                         ib_cxt.mapping.dhcp_members[0].member_id)
        self.assertEqual(expected_dns_members, ib_cxt.mapping.dns_members)

    def test_reserve_service_members_without_ib_network_for_gm_authortity(
            self):
        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id-gm', 'member_type': 'GM',
             'member_ip': '11.11.1.11', 'member_ipv6': None,
             'member_dns_ip': '12.11.1.11', 'member_dns_ipv6': None,
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_name': 'gm', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        self._test_reserve_service_members_without_ib_network_for_gm_auth(
            test_authority_member, True, [test_authority_member])
        self._test_reserve_service_members_without_ib_network_for_gm_auth(
            test_authority_member, False, [])

    def _test_reserve_service_members_with_ib_network_gm_owned(
            self, dns_support):
        user_id = 'test user'
        tenant_id = 'tenant-id'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True
        self.grid_config.dns_support = dns_support

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt._register_services = mock.Mock()
        dhcp_members = dbi.get_service_members(
            self.ctx.session,
            network_view_id=ib_cxt.mapping.network_view_id,
            service=const.SERVICE_TYPE_DHCP)
        expected_dhcp_member = dhcp_members[0]

        # ib network with no members and options
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='default',
                                               cidr='12.12.1.0/24')
        test_ib_network.members = []
        test_ib_network.options = []

        ib_cxt.reserve_service_members(test_ib_network)

        expected_dns_members = (
            ib_cxt.mapping.dhcp_members if dns_support else [])
        self.assertEqual(expected_dhcp_member.member_id,
                         ib_cxt.mapping.dhcp_members[0].member_id)
        self.assertEqual(expected_dns_members, ib_cxt.mapping.dns_members)
        actual_opt_router = [opt for opt in test_ib_network.options
                             if opt.name == 'routers']
        self.assertEqual(subnet['gateway_ip'], actual_opt_router[0].value)

    def test_reserve_service_members_with_ib_network_gm_owned(self):
        self._test_reserve_service_members_with_ib_network_gm_owned(True)
        self._test_reserve_service_members_with_ib_network_gm_owned(False)

    def _test_reserve_service_members_with_ib_network_with_dhcp_member(
            self, test_dhcp_member, dns_support, expected_dns_members):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True
        self.grid_config.dns_support = dns_support

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt._register_services = mock.Mock()
        ib_cxt._get_dhcp_members = mock.Mock(return_value=[test_dhcp_member])
        ib_cxt._get_dns_members = mock.Mock(return_value=[test_dhcp_member])

        # ib network with dhcp member assigned
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='test-view',
                                               cidr='12.12.1.0/24')
        test_ib_network.members = [
            ib_objects.AnyMember(_struct='dhcpmember',
                                 name=test_dhcp_member.member_name,
                                 ipv4addr=test_dhcp_member.member_ip)]
        test_ib_network.options = [
            ib_objects.DhcpOption(name='domain-name-servers',
                                  value=test_dhcp_member.member_ip)]

        ib_cxt.reserve_service_members(test_ib_network)

        self.assertEqual([test_dhcp_member], ib_cxt.mapping.dhcp_members)
        self.assertEqual(expected_dns_members, ib_cxt.mapping.dns_members)
        actual_opt_router = [opt for opt in test_ib_network.options
                             if opt.name == 'routers']
        self.assertEqual(subnet['gateway_ip'], actual_opt_router[0].value)

    def test_reserve_service_members_with_ib_network_with_dhcp_member(self):
        test_dhcp_member = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'REGULAR',
             'member_ip': '11.11.1.12', 'member_ipv6': None,
             'member_dns_ip': '12.11.1.11', 'member_dns_ipv6': None,
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        self._test_reserve_service_members_with_ib_network_with_dhcp_member(
            test_dhcp_member,
            dns_support=True, expected_dns_members=[test_dhcp_member])
        self._test_reserve_service_members_with_ib_network_with_dhcp_member(
            test_dhcp_member,
            dns_support=False, expected_dns_members=[])

    def _test_reserve_service_members_with_ib_network_without_dhcp_member(
            self, dns_support):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True
        self.grid_config.dns_support = dns_support

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt._register_services = mock.Mock()

        # ib network with dhcp member and gateway ips assigned
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='test-view',
                                               cidr='12.12.1.0/24')
        test_ib_network.members = [
            ib_objects.AnyMember(
                _struct='dhcpmember',
                name=ib_cxt.mapping.authority_member.member_name)]
        test_gateway_ip = '12.12.1.1'
        test_ib_network.options = [
            ib_objects.DhcpOption(name='routers', value=test_gateway_ip)]

        ib_cxt.reserve_service_members(test_ib_network)

        expected_dns_members = (
            [ib_cxt.mapping.authority_member] if dns_support else [])
        # authority member is CPM, so dhcp/dns member should be the same as
        # authority member
        self.assertEqual([ib_cxt.mapping.authority_member],
                         ib_cxt.mapping.dhcp_members)
        self.assertEqual(expected_dns_members,
                         ib_cxt.mapping.dns_members)
        actual_opt_router = [opt for opt in test_ib_network.options
                             if opt.name == 'routers']
        self.assertEqual(subnet['gateway_ip'] + ',' + test_gateway_ip,
                         actual_opt_router[0].value)

    def test_reserve_service_members_with_ib_network_without_dhcp_member(self):
        self._test_reserve_service_members_with_ib_network_without_dhcp_member(
            True)
        self._test_reserve_service_members_with_ib_network_without_dhcp_member(
            False)

    def test_get_dns_members_without_dhcp_support(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = False

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)

        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id', 'member_type': 'GM',
             'member_ip': '11.11.1.11', 'member_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        ib_cxt.mapping.authority_member = test_authority_member

        grid_primaries, grid_secondaries = ib_cxt.get_dns_members()

        expected_grid_primaries = [
            ib_objects.AnyMember(_struct='memberserver',
                                 name=test_authority_member.member_name)]
        self.assertEqual(expected_grid_primaries[0].name,
                         grid_primaries[0].name)
        self.assertEqual(None, grid_secondaries)

    def test_get_dns_members_with_dhcp_support(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dhcp_support = True

        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)

        test_authority_member = utils.json_to_obj(
            'AuthorityMember',
            {'member_id': 'member-id', 'member_type': 'GM',
             'member_ip': '11.11.1.11', 'member_ipv6': None,
             'member_name': 'gm', 'member_status': 'ON',
             'member_wapi': '11.11.1.11'})
        ib_cxt.mapping.authority_member = test_authority_member

        test_dhcp_member_1 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'REGULAR',
             'member_ip': '11.11.1.12', 'member_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON',
             'member_wapi': '11.11.1.12'})
        test_dhcp_member_2 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'CPM',
             'member_ip': '11.11.1.13', 'member_ipv6': None,
             'member_name': 'm2', 'member_status': 'ON',
             'member_wapi': '11.11.1.13'})
        ib_cxt.mapping.dhcp_members = [test_dhcp_member_1, test_dhcp_member_2]
        ib_cxt.mapping.dns_members = [test_dhcp_member_1, test_dhcp_member_2]

        grid_primaries, grid_secondaries = ib_cxt.get_dns_members()

        expected_primaries = [
            ib_objects.AnyMember(_struct='memberserver',
                                 name=test_authority_member.member_name)]
        expected_secondaries = [
            ib_objects.AnyMember(_struct='memberserver',
                                 name=test_dhcp_member_1.member_name),
            ib_objects.AnyMember(_struct='memberserver',
                                 name=test_dhcp_member_2.member_name)]
        self.assertEqual(expected_primaries, grid_primaries)
        self.assertEqual(expected_secondaries, grid_secondaries)

    def test_get_ip_allocator_for_hosts(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b05524826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.1.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        self.grid_config.dns_support = True
        self.grid_config.ip_allocation_strategy = (
            const.IP_ALLOCATION_STRATEGY_HOST_RECORD)
        self.grid_config.zone_creation_strategy = (
            const.GRID_CONFIG_DEFAULTS[
                const.EA_GRID_CONFIG_ZONE_CREATION_STRATEGY])
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ip_allocator = ib_cxt._get_ip_allocator()
        self.assertEqual(True, ip_allocator.opts['configure_for_dns'])

        self.grid_config.dns_support = False
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ip_allocator = ib_cxt._get_ip_allocator()
        self.assertEqual(False, ip_allocator.opts['configure_for_dns'])

        self.grid_config.dns_support = True
        self.grid_config.zone_creation_strategy = [
            const.ZONE_CREATION_STRATEGY_REVERSE]
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ip_allocator = ib_cxt._get_ip_allocator()
        self.assertEqual(False, ip_allocator.opts['configure_for_dns'])
