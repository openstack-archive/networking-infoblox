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

from neutron import context
from neutron.ipam.drivers.infoblox.common import constants as const
from neutron.ipam.drivers.infoblox.db import db_api
from neutron.tests.unit import testlib_api


class TestDbManager(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestDbManager, self).setUp()
        self.ctx = context.get_admin_context()
        self.member_id_m1 = 'm1'
        self.member_id_m2 = 'm2'
        #self.ctx.session.flush()

    # def _create_member(self, member_id, member_name, ipv4addr, ipv6addr=None,
    #                    service_type, member_status):
    #     db_api.add_member(self.ctx.session,
    #                       member_id,
    #                       member_name,
    #                       ipv4addr,
    #                       conf.get('ipv6addr', None),
    #                       conf['type'],
    #                       conf['status'])

    def test_member_crud_operations(self):
        db_api.add_member(self.ctx.session, 'm1', 'member1.com',
                          '192.168.1.10', None,
                          const.MEMBER_TYPE_DHCP, 'ON')
        members = db_api.get_members(self.ctx.session)
        self.assertEqual(1, len(members))
        #print members

    def test_member_mapping(self):
        members = db_api.reserve_members(
            self.ctx.session,
            member_ids=["m1", "m2"],
            services=[const.SERVICE_TYPE_DHCP, const.SERVICE_TYPE_DNS],
            mapping_id="myview",
            scope=const.MEMBER_MAPPING_SCOPE_NETWORK_VIEW)
        self.assertEqual(4, len(members))
