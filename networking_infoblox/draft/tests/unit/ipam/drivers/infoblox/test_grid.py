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

import io

from oslo_serialization import jsonutils

from neutron import context
from neutron.ipam.drivers.infoblox.common import grid
from neutron.ipam.drivers.infoblox.common import utils
from neutron.ipam.drivers.infoblox.db import db_api
from neutron.tests.unit import testlib_api


GRID_COUNT = 2


class TestGridManagerMixin(object):

    def _create_member_config_stream(self, member_count):
        member_config = [{
            "grid_id": "grid1",
            "grid_name": "grid 1",
            "grid_connection": {
                "wapi_version": "2.0",
                "wapi_ssl_verify": False,
                "wapi_http_pool_connections": 100,
                "wapi_http_pool_maxsize": 100,
                "wapi_http_request_timeout": 120,
                "wapi_admin_user": {"name": "admin", "password": "infoblox"},
                "wapi_cloud_user": {"name": "cloud-api-user",
                                    "password": "infoblox"}
            },
            "grid_members": [
                {
                    "member_id": "grid1-member%d" % i,
                    "member_ip": "192.168.1.%d" % i,
                    "member_ipv6": "fddb:456d:1217:717c::1%d" % i,
                    "member_name": "grid1.member%d.com" % i,
                    "member_type": "MEMBER",
                    "member_status": "ON"
                } for i in range(1, member_count + 1)
            ]
        }, {
            "grid_id": "grid2",
            "grid_name": "grid 2",
            "grid_connection": {
                "wapi_version": "2.0",
                "wapi_ssl_verify": False,
                "wapi_http_pool_connections": 100,
                "wapi_http_pool_maxsize": 100,
                "wapi_http_request_timeout": 120,
                "wapi_admin_user": {"name": "admin", "password": "infoblox"},
                "wapi_cloud_user": {"name": "cloud-api-user",
                                    "password": "infoblox"}
            },
            "grid_members": [
                {
                    "member_id": "grid2-member%d" % i,
                    "member_ip": "192.168.2.%d" % i,
                    "member_ipv6": "fddb:456d:1217:717c::2%d" % i,
                    "member_name": "grid2.member%d.com" % i,
                    "member_type": "MEMBER",
                    "member_status": "ON"
                } for i in range(1, member_count + 1)
            ]
        }]
        config_stream = io.BytesIO(jsonutils.dumps(member_config))
        return config_stream.read()

    def _get_member_manager_with_members(self, ctx, member_count):
        config_stream = self._create_member_config_stream(member_count)
        manager = grid.GridMemberManager(ctx, config_stream)
        return manager

    def _create_condition_config_stream(self,
                                        grid_id,
                                        tenant_network_view='{tenant_id}',
                                        tenant_is_delegated_view=True,
                                        global_network_view='default',
                                        global_dhcp_members=["master"]):
        condition_config = [
            {
                "condition": "tenant",
                "grid_id": grid_id,
                "is_external": False,
                "network_view": tenant_network_view,
                "is_delegated_view": tenant_is_delegated_view,
                "dhcp_members": "<next-available-member>",
                "require_dhcp_relay": True,
                "domain_suffix_pattern": "{subnet_id}.cloud.global.com",
                "hostname_pattern": "host-{ip_address}"
            },
            {
                "condition": "global",
                "grid_id": grid_id,
                "is_delegated_view": False,
                "reserved_member": global_dhcp_members[0],
                "is_external": True,
                "network_view": global_network_view,
                "dhcp_members": global_dhcp_members,
                "require_dhcp_relay": True,
                "domain_suffix_pattern": "{subnet_id}.cloud.global.com",
                "hostname_pattern": "host-{ip_address}"
            }
        ]
        config_stream = io.BytesIO(jsonutils.dumps(condition_config))
        return config_stream.read()

    def _get_config_manager(self, ctx, **kwargs):
        config_stream = self._create_condition_config_stream(**kwargs)
        manager = grid.GridConfigManager(ctx, config_stream)
        return manager

    def _verify_grids(self, grids):
        grid_idx = 1
        for g in grids:
            self.assertEqual("grid%d" % grid_idx, g.grid_id)
            self.assertEqual("grid %d" % grid_idx, g.grid_name)
            connection_info = utils.json_to_obj('Connection',
                                                g.grid_connection)
            self.assertEqual("2.0", connection_info.wapi_version)
            self.assertEqual(False, connection_info.wapi_ssl_verify)
            self.assertEqual(100, connection_info.wapi_http_pool_connections)
            self.assertEqual("admin", connection_info.wapi_admin_user.name)
            self.assertEqual("cloud-api-user",
                             connection_info.wapi_cloud_user.name)
            grid_idx += 1

    def _verify_members(self, members):
        member_idx = 1
        grid_idx = 1
        member_count = len(members)
        member_count_per_grid = member_count / GRID_COUNT
        for member in members:
            self.assertEqual("grid%d-member%d" % (grid_idx, member_idx),
                             member.member_id)
            self.assertEqual("192.168.%d.%d" % (grid_idx, member_idx),
                             member.member_ip)
            self.assertEqual(
                "fddb:456d:1217:717c::%d%d" % (grid_idx, member_idx),
                member.member_ipv6)
            self.assertEqual(
                "grid%d.member%d.com" % (grid_idx, member_idx),
                member.member_name)
            self.assertEqual("MEMBER", member.member_type)
            self.assertEqual("ON", member.member_status)
            if (member_count - member_idx) % member_count_per_grid == 0:
                grid_idx += 1
                member_idx = 1
            else:
                member_idx += 1


class TestGridMemberManager(testlib_api.SqlTestCase, TestGridManagerMixin):

    def setUp(self):
        super(TestGridMemberManager, self).setUp()
        self.ctx = context.get_admin_context()

    def test_sync(self):
        member_count_per_grid = 5
        total_member_count = GRID_COUNT * member_count_per_grid
        #import pdb; pdb.set_trace()
        manager = self._get_member_manager_with_members(self.ctx,
                                                        member_count_per_grid)
        manager.sync()

        grids = db_api.get_grids(self.ctx.session)
        grids = utils.db_records_to_obj('Grid', grids)
        #import pdb; pdb.set_trace()
        self.assertEqual(GRID_COUNT, len(grids))
        self._verify_grids(grids)

        members = db_api.get_members(self.ctx.session)
        members = utils.db_records_to_obj('Member', members)

        self.assertEqual(total_member_count, len(members))
        self._verify_members(members)

        # calling sync again should not cause any change
        manager.sync()
        members = db_api.get_members(self.ctx.session)
        members = utils.db_records_to_obj('Member', members)
        self.assertEqual(total_member_count, len(members))
        self._verify_members(members)


class TestGridConfigManager(testlib_api.SqlTestCase, TestGridManagerMixin):

    def setUp(self):
        super(TestGridConfigManager, self).setUp()
        self.ctx = context.get_admin_context()

    def test_sync(self):
        member_count_per_grid = 3
        total_member_count = GRID_COUNT * member_count_per_grid
        gm_manager = self._get_member_manager_with_members(
            self.ctx, member_count_per_grid)
        gm_manager.sync()
        members = db_api.get_members(self.ctx.session)
        self.assertEqual(total_member_count, len(members))
        self._verify_members(members)

        grid_id = "grid1"
        global_network_view = 'default'
        global_dhcp_members = ["grid1-member1", "grid1-member2"]

        gc_manager = self._get_config_manager(
            self.ctx,
            grid_id=grid_id,
            global_network_view=global_network_view,
            global_dhcp_members=global_dhcp_members)
        gc_manager.sync()

        # No change in member registration
        members = db_api.get_members(self.ctx.session)
        self.assertEqual(total_member_count, len(members))
        self._verify_members(members)

        reserved_members = db_api.get_reserved_members(self.ctx.session)
        # expected reserved members should be 4 since two members are mapping
        # by global_dhcp_members and each member is reserved for DHCP and DNS
        # services
        self.assertEqual(len(global_dhcp_members) * 2, len(reserved_members))

        # calling sync again should not cause any change
        gc_manager.sync()
        reserved_members = db_api.get_reserved_members(self.ctx.session)
        self.assertEqual(len(global_dhcp_members) * 2, len(reserved_members))

        # reserved_members = db_api.get_reserved_members(self.ctx.session,
        #                                                #service=const.MEMBER_TYPE_DHCP,
        #                                                mapping_id=global_network_view,
        #                                                allow_member_detail=True)
        #reserved_members_json = utils.db_records_to_json(reserved_members)

        # network = {
        #     'network_id': 'some-net-id',
        #     'name': 'some-net-name',
        #     'tenant_id': 'some-tenant-id',
        #     'router:external': True
        # }
        # subnet = {
        #     'network_id': 'some-net-id',
        #     'cidr': '192.168.1.0/24',
        #     'tenant_id': 'some-tenant-id'
        # }
        # cfg = gc_manager.get_subnet_config(network, subnet)
        #cfg._pattern_builder.build_hostname()


class TestGriManager(testlib_api.SqlTestCase, TestGridManagerMixin):

    def setUp(self):
        super(TestGriManager, self).setUp()
        self.ctx = context.get_admin_context()

        self.grid_id = "grid1"
        self.global_network_view = 'default'
        self.global_dhcp_members = ["grid1-member1", "grid1-member2"]

        self.member_count_per_grid = 3
        self.total_member_count = GRID_COUNT * self.member_count_per_grid
        self.member_config_stream = \
            self._create_member_config_stream(self.member_count_per_grid)
        self.condition_config_stream = \
            self._create_condition_config_stream(
                grid_id=self.grid_id,
                global_network_view=self.global_network_view,
                global_dhcp_members=self.global_dhcp_members)

    def test_sync(self):
        manager = grid.GridManager(self.ctx,
                                   self.member_config_stream,
                                   self.condition_config_stream)
        manager.sync()

        registered_members = db_api.get_members(self.ctx.session)
        self.assertEqual(self.total_member_count, len(registered_members))

        reserved_members = db_api.get_reserved_members(self.ctx.session)
        self.assertEqual(len(self.global_dhcp_members) * 2,
                         len(reserved_members))

        # calling sync again should not cause any change
        manager.sync()
        self.assertEqual(self.total_member_count, len(registered_members))
        self.assertEqual(len(self.global_dhcp_members) * 2,
                         len(reserved_members))
