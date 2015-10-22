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
        self.grid_mgr.sync()

        self.grid_id = self.grid_mgr.grid_config.grid_id
        self.grid_config = self.grid_mgr.grid_config

    def test_get_network_view_default_mapping_single(self):
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

    def test_get_network_view_default_mapping_tenant(self):
        user_id = 'test user'
        tenant_id = 'test-tenant-id'
        tenant_name = 'test-tenant-name'

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
        ib_cxt._get_tenant_name = mock.Mock()

        # validate the mapping network view
        expected_netview = utils.generate_network_view_name(tenant_id,
                                                            tenant_name)
        self.assertIsNone(ib_cxt.mapping.network_view_id)
        self.assertEqual(expected_netview,
                         ib_cxt.mapping.network_view)
        self.assertEqual(None,
                         ib_cxt.mapping.authority_member)

    def test_get_network_view_mapping_tenant_id_condition(self):
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

    def test_get_network_view_mapping_tenant_cidr(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr tat is not used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.2.0/24'
        subnet = self.plugin_stub.create_subnet(tenant_id, subnet_name,
                                                network['id'], subnet_cidr)

        # make sure that subnet cidr is used in mapping condition for tenant
        # cidr; for tenant cidr, any subnet under tenant should contain
        # this cidr
        db_conditions = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_value=subnet_cidr)
        self.assertEqual(1, len(db_conditions))

        # test mapping where both tenant id and tenant cidr match
        ib_cxt = ib_context.InfobloxContext(self.ctx, user_id, network, subnet,
                                            self.grid_config, self.plugin)
        ib_cxt.connector = mock.Mock()
        ib_cxt.ibom = mock.Mock()
        ib_cxt.ip_allocator = mock.Mock()

        # validate the mapping network view
        matching_cond_1 = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_name='Tenant ID Mapping',
            neutron_object_value=tenant_id)
        matching_netviews_1 = utils.get_values_from_records('network_view_id',
                                                            matching_cond_1)
        matching_cond_2 = dbi.get_mapping_conditions(
            self.ctx.session,
            grid_id=self.grid_id,
            neutron_object_name='Tenant CIDR Mapping',
            neutron_object_value=subnet_cidr)
        matching_netviews_2 = utils.get_values_from_records('network_view_id',
                                                            matching_cond_2)
        matching_netviews = list(set.intersection(set(matching_netviews_1),
                                                  set(matching_netviews_2)))

        expected_netview_id = matching_netviews[0]
        netview_row = utils.find_one_in_list('id', expected_netview_id,
                                             ib_cxt.discovered_network_views)
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

    def test_get_network_view_mapping_already_exists(self):
        user_id = 'test user'
        tenant_id = '90fbad5a098a4b7cb98826128d5b40b3'

        # prepare network
        network_name = 'Test Network'
        network = self.plugin_stub.create_network(tenant_id, network_name)

        # prepare subnet with cidr tat is not used in mapping conditions
        subnet_name = 'Test Subnet'
        subnet_cidr = '11.11.2.0/24'
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
