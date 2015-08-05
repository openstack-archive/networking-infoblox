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

import six

from oslo_serialization import jsonutils

from neutron import context
from neutron.ipam.drivers.infoblox.common import utils
from neutron.ipam.drivers.infoblox.db import db_api
from neutron.tests.unit import testlib_api


class TestUtils(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestUtils, self).setUp()
        self.ctx = context.get_admin_context()

    def test_json_to_obj(self):
        json_obj = {'a': 1, 'b': {'c': {'d': 2}}}
        my_object = utils.json_to_obj('MyObject', json_obj)
        self.assertEqual(1, my_object.a)
        self.assertEqual(type(my_object.b), type(my_object))
        self.assertEqual(type(my_object.b.c), type(my_object))
        self.assertEqual(2, my_object.b.c.d)

        json_string = "{'a': 1, 'b': {'c': {'d': 2}}}'"
        my_object = utils.json_to_obj('MyObject', json_string)
        self.assertEqual(1, my_object.a)
        self.assertEqual(type(my_object.b), type(my_object))
        self.assertEqual(type(my_object.b.c), type(my_object))
        self.assertEqual(2, my_object.b.c.d)

    def test_get_values_from_records(self):
        db_api.add_grid(self.ctx.session, 'grid-1', 'test grid 1', '{}')
        db_api.add_grid(self.ctx.session, 'grid-2', 'test grid 2', '{}')

        grids = db_api.get_grids(self.ctx.session)

        grid_ids = utils.get_values_from_records('grid_id', grids)

        self.assertEqual(2, len(grid_ids))
        self.assertEqual('grid-1', grid_ids[0])
        self.assertEqual('grid-2', grid_ids[1])

        grid_names = utils.get_values_from_records('grid_name', grids)
        self.assertEqual(2, len(grid_ids))
        self.assertEqual('test grid 1', grid_names[0])
        self.assertEqual('test grid 2', grid_names[1])

    def test_db_records_to_json(self):
        db_api.add_grid(self.ctx.session, 'grid-1', 'test grid 1',
                        '{"wapi_version": "2.0",'
                        '"wapi_admin_user": '
                        '{ "name": "admin", "password": "infoblox" }}')
        db_api.add_grid(self.ctx.session, 'grid-2', 'test grid 2', '{}')

        grids = db_api.get_grids(self.ctx.session)

        json = utils.db_records_to_json(grids)

        self.assertEqual('test grid 1', json[0]["grid_name"])
        self.assertEqual('test grid 2', json[1]["grid_name"])

        json_string = json[0]["grid_connection"]
        grid_connection_json = jsonutils.loads(json_string)

        self.assertIsInstance(json_string, six.string_types)
        self.assertIsInstance(grid_connection_json, dict)
        self.assertEqual('2.0', grid_connection_json['wapi_version'])
        self.assertEqual('admin',
                         grid_connection_json['wapi_admin_user']['name'])

        grid_connection = utils.json_to_obj('grid_connection',
                                            grid_connection_json)
        self.assertEqual('2.0', grid_connection.wapi_version)
        self.assertEqual('admin', grid_connection.wapi_admin_user.name)

        self.assertEqual('{}', json[1]["grid_connection"])
        self.assertEqual({}, jsonutils.loads(json[1]["grid_connection"]))

    def test_db_records_to_obj(self):
        db_api.add_grid(self.ctx.session, 'grid-1', 'test grid 1',
                        '{"wapi_version": "2.0",'
                        '"wapi_admin_user": '
                        '{ "name": "admin", "password": "infoblox" }}')
        db_api.add_grid(self.ctx.session, 'grid-2', 'test grid 2', '{}')

        grids = db_api.get_grids(self.ctx.session)
        grid_obj = utils.db_records_to_obj('Grid', grids)

        self.assertEqual('test grid 1', grid_obj[0].grid_name)
        self.assertEqual('test grid 1', grid_obj[0].get('grid_name'))
        self.assertEqual('test grid 1', grid_obj[0]['grid_name'])
        self.assertEqual('test grid 2', grid_obj[1].grid_name)
        self.assertEqual('test grid 2', grid_obj[1].get('grid_name'))
        self.assertEqual('test grid 2', grid_obj[1]['grid_name'])

        grid_connection = jsonutils.loads(grid_obj[0].grid_connection)
        self.assertEqual('admin', grid_connection["wapi_admin_user"]["name"])

    def test_scalar_from_ea(self):
        ea = {"extattrs": {"Cloud API Owned": {"value": "True"},
                           "CMP Type": {"value": "Openstack"},
                           "Subnet ID": {"value": "subnet-22222222"}}}
        cloud_api_owned_ea = utils.scalar_from_ea("Cloud API Owned", ea)
        self.assertEqual('True', cloud_api_owned_ea)
        cmp_type_ea = utils.scalar_from_ea("CMP Type", ea)
        self.assertEqual('Openstack', cmp_type_ea)
        subnet_id_ea = utils.scalar_from_ea("Subnet ID", ea)
        self.assertEqual('subnet-22222222', subnet_id_ea)

        # negative tests
        invalid_ea = utils.scalar_from_ea("Invalid", ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.scalar_from_ea(None, ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.scalar_from_ea(None, None)
        self.assertEqual(None, invalid_ea)

    def test_is_valid_ip(self):
        self.assertEqual(False, utils.is_valid_ip('1.1.1.1.1'))
        self.assertEqual(False, utils.is_valid_ip('2001:gg:1'))
        self.assertEqual(False, utils.is_valid_ip('a.b.c.d'))
        self.assertEqual(True, utils.is_valid_ip('1.1.1.1'))
        self.assertEqual(True, utils.is_valid_ip('2001:ff::1'))

    def test_generate_duid(self):
        # DUID mac address starts from position 12
        duid_mac_start_point = 12

        duid_count = 10
        mac = 'fa:16:3e:bd:ce:14'
        duids = [utils.generate_duid(mac) for _ in range(duid_count)]

        matching = [True for e in duids
                    if e.find(mac) == duid_mac_start_point]
        self.assertEqual(len({}.fromkeys(duids)), len(duids))
        self.assertEqual(duid_count, len(matching))

        duid_count = 50
        mac = 'fa:16:3e:1d:79:d7'
        duids = [utils.generate_duid(mac) for _ in range(duid_count)]

        matching = [True for e in duids
                    if e.find(mac) == duid_mac_start_point]
        self.assertEqual(len({}.fromkeys(duids)), len(duids))
        self.assertEqual(duid_count, len(matching))
