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

from networking_infoblox.neutron.db import infoblox_db


class InfobloxDbTestCase(testlib_api.SqlTestCase):

    def setUp(self):
        super(InfobloxDbTestCase, self).setUp()
        self.ctx = context.get_admin_context()

    def test_grid_management(self):
        grid_1_id = 100
        grid_1_name = "Test Grid 1000"
        grid_1_connection = "{}"
        grid_2_id = 200
        grid_2_name = "Test Grid 2000"
        grid_2_connection = "{}"

        # expects no grid
        grids = infoblox_db.get_grids(self.ctx.session)
        self.assertEqual(0, len(grids))

        # add two grids
        infoblox_db.add_grid(self.ctx.session, grid_1_id, grid_1_name,
                             grid_1_connection)
        infoblox_db.add_grid(self.ctx.session, grid_2_id, grid_2_name,
                             grid_2_connection)

        grids = infoblox_db.get_grids(self.ctx.session)
        self.assertEqual(2, len(grids))

        grids = infoblox_db.get_grids(self.ctx.session, grid_1_id)
        self.assertEqual(grid_1_id, grids[0]['grid_id'])
        self.assertEqual(grid_1_name, grids[0]['grid_name'])

        grids = infoblox_db.get_grids(self.ctx.session, grid_2_id,
                                      grid_2_name)
        self.assertEqual(grid_2_id, grids[0]['grid_id'])
        self.assertEqual(grid_2_name, grids[0]['grid_name'])

        # update grid 1
        grid_1_name_update = "Test Grid 1000 Enhanced"
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
                                grid_1_id,
                                grid_1_name_update,
                                grid_connection_json_string)
        grids = infoblox_db.get_grids(self.ctx.session, grid_1_id)
        self.assertEqual(grid_1_name_update, grids[0]['grid_name'])
        self.assertEqual(grid_connection_json_string,
                         grids[0]['grid_connection'])

        # remove grid 1
        infoblox_db.remove_grids(self.ctx.session, [grid_1_id])

        grids = infoblox_db.get_grids(self.ctx.session, grid_1_id)
        self.assertEqual(0, len(grids))

        # remove two grids
        infoblox_db.add_grid(self.ctx.session, grid_1_id, grid_1_name,
                             grid_1_connection)
        infoblox_db.remove_grids(self.ctx.session, [grid_1_id, grid_2_id])

        grids = infoblox_db.get_grids(self.ctx.session)
        self.assertEqual(0, len(grids))

    def test_member_management(self):
        grid_id = 100
        grid_name = "Test Grid 1000"
        grid_connection = "{}"
        member_1_id = 'M_1000'
        member_1_name = "Member 1000"
        member_1_ip = "10.10.1.12"
        member_1_ipv6 = None
        member_1_type = "REGULAR"
        member_1_status = "WORKING"
        member_2_id = 'M_2000'
        member_2_name = "Member 2000"
        member_2_ip = "10.10.1.22"
        member_2_ipv6 = "fd44:acb:5df6:1083::22"
        member_2_type = "CPM"
        member_2_status = "WORKING"

        # expects no member
        members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(0, len(members))

        infoblox_db.add_grid(self.ctx.session, grid_id, grid_name,
                             grid_connection)
        self.ctx.session.flush()

        # add two members
        infoblox_db.add_member(self.ctx.session, member_1_id, grid_id,
                               member_1_name, member_1_ip, member_1_ipv6,
                               member_1_type, member_1_status)
        infoblox_db.add_member(self.ctx.session, member_2_id, grid_id,
                               member_2_name, member_2_ip, member_2_ipv6,
                               member_2_type, member_2_status)

        members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(2, len(members))
        self.assertEqual(member_2_id, members[1]['member_id'])
        self.assertEqual(grid_id, members[1]['grid_id'])
        self.assertEqual(member_2_name, members[1]['member_name'])
        self.assertEqual(member_2_ip, members[1]['member_ip'])
        self.assertEqual(member_2_ipv6, members[1]['member_ipv6'])
        self.assertEqual(member_2_status, members[1]['member_status'])

        members = infoblox_db.get_members(self.ctx.session, member_1_id)
        self.assertEqual(member_1_id, members[0]['member_id'])
        self.assertEqual(grid_id, members[0]['grid_id'])
        self.assertEqual(member_1_name, members[0]['member_name'])
        self.assertEqual(member_1_ip, members[0]['member_ip'])
        self.assertEqual(member_1_ipv6, members[0]['member_ipv6'])
        self.assertEqual(member_1_status, members[0]['member_status'])

        # update member
        member_1_name_update = "Member 1000 VM"
        member_1_ipv6_update = "fd44:acb:5df6:1083::12"
        infoblox_db.update_member(self.ctx.session, member_1_id,
                                  grid_id, member_1_name_update,
                                  member_1_ip, member_1_ipv6_update,
                                  member_1_type, member_1_status)
        members = infoblox_db.get_members(self.ctx.session, member_1_id)
        self.assertEqual(member_1_name_update, members[0]['member_name'])
        self.assertEqual(member_1_ipv6_update, members[0]['member_ipv6'])

        # remove member 1
        infoblox_db.remove_members(self.ctx.session, [member_1_id])
        members = infoblox_db.get_members(self.ctx.session, member_1_id)
        self.assertEqual(0, len(members))

        infoblox_db.add_member(self.ctx.session, member_1_id, grid_id,
                               member_1_name, member_1_ip, member_1_ipv6,
                               member_1_type, member_1_status)
        members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(2, len(members))

        # remove all members
        infoblox_db.remove_members(self.ctx.session,
                                   [member_1_id, member_2_id])
        members = infoblox_db.get_members(self.ctx.session)
        self.assertEqual(0, len(members))

        infoblox_db.remove_grids(self.ctx.session, [grid_id])
