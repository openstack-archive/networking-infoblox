# Copyright 2015 Infoblox Inc.
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

import netaddr
import six

from oslo_serialization import jsonutils

from neutron import context
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


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
        json_string = '{"a": 1, "b": {"c": {"d": 2}}}'
        my_object = utils.json_to_obj('MyObject', json_string)
        self.assertEqual(1, my_object.a)
        self.assertEqual(type(my_object.b), type(my_object))
        self.assertEqual(type(my_object.b.c), type(my_object))
        self.assertEqual(2, my_object.b.c.d)

    def test_get_values_from_records(self):
        grid_1_id = 100
        grid_2_id = 200
        dbi.add_grid(self.ctx.session, grid_1_id, 'test grid 1', '{}', 'ON')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'OFF')

        grids = dbi.get_grids(self.ctx.session)
        grid_ids = utils.get_values_from_records('grid_id', grids)

        self.assertEqual(2, len(grid_ids))
        self.assertEqual(grid_1_id, grid_ids[0])
        self.assertEqual(grid_2_id, grid_ids[1])

        grid_names = utils.get_values_from_records('grid_name', grids)
        self.assertEqual(2, len(grid_ids))
        self.assertEqual('test grid 1', grid_names[0])
        self.assertEqual('test grid 2', grid_names[1])

    def test_db_records_to_json(self):
        grid_1_id = 100
        grid_2_id = 200
        dbi.add_grid(self.ctx.session, grid_1_id, 'test grid 1',
                     '{"wapi_version": "2.0",'
                     '"wapi_admin_user": '
                     '{ "name": "admin", "password": "infoblox" }}',
                     'ON')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'OFF')

        grids = dbi.get_grids(self.ctx.session)

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
        grid_1_id = 100
        grid_2_id = 200
        dbi.add_grid(self.ctx.session, grid_1_id, 'test grid 1',
                     '{"wapi_version": "2.0",'
                     '"wapi_admin_user": '
                     '{ "name": "admin", "password": "infoblox" }}',
                     'ON')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'ON')

        grids = dbi.get_grids(self.ctx.session)
        grid_obj = utils.db_records_to_obj('Grid', grids)

        self.assertEqual('test grid 1', grid_obj[0].grid_name)
        self.assertEqual('test grid 1', grid_obj[0].get('grid_name'))
        self.assertEqual('test grid 1', grid_obj[0]['grid_name'])
        self.assertEqual('test grid 2', grid_obj[1].grid_name)
        self.assertEqual('test grid 2', grid_obj[1].get('grid_name'))
        self.assertEqual('test grid 2', grid_obj[1]['grid_name'])

        grid_connection = jsonutils.loads(grid_obj[0].grid_connection)
        self.assertEqual('admin', grid_connection["wapi_admin_user"]["name"])

    def test_construct_ea(self):
        attributes = {"key1": "value1", "key2": "value2"}
        ea = utils.construct_ea(attributes)
        self.assertEqual({'value': 'value1'}, ea['key1'])
        self.assertEqual({'value': 'value2'}, ea['key2'])
        self.assertEqual({'value': 'OpenStack'}, ea['CMP Type'])

        attributes = dict()
        ea = utils.construct_ea(attributes)
        self.assertEqual({'CMP Type': {'value': 'OpenStack'}}, ea)

    def test_get_string_or_none(self):
        value = ""
        my_string = utils.get_string_or_none(value)
        self.assertEqual(value, my_string)

        value = None
        my_string = utils.get_string_or_none(value)
        self.assertEqual(value, my_string)

        value = 2
        my_string = utils.get_string_or_none(value)
        self.assertEqual(str(value), my_string)

        value = ['test string']
        my_string = utils.get_string_or_none(value)
        self.assertEqual(str(value), my_string)

        value = ['test string 1', 'test string 2']
        my_string = utils.get_string_or_none(value)
        self.assertEqual(str(value), my_string)

    def test_get_ea_value(self):
        ea = {"extattrs": {"Cloud API Owned": {"value": "True"},
                           "CMP Type": {"value": "Openstack"},
                           "Subnet ID": {"value": "subnet-22222222"}}}
        cloud_api_owned_ea = utils.get_ea_value("Cloud API Owned", ea)
        self.assertEqual('True', cloud_api_owned_ea)
        cmp_type_ea = utils.get_ea_value("CMP Type", ea)
        self.assertEqual('Openstack', cmp_type_ea)
        subnet_id_ea = utils.get_ea_value("Subnet ID", ea)
        self.assertEqual('subnet-22222222', subnet_id_ea)

        # negative tests
        invalid_ea = utils.get_ea_value("Invalid", ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.get_ea_value(None, ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.get_ea_value(None, None)
        self.assertEqual(None, invalid_ea)

    def test_get_ip_version(self):
        ips = ('10.10.0.1', '8.8.8.8')
        for ip in ips:
            self.assertEqual(4, utils.get_ip_version(ip))

        ips = ('fffe::1', '2001:ff::1')
        for ip in ips:
            self.assertEqual(6, utils.get_ip_version(ip))

        # invalid addresses
        ips = ('1.0.1.555', '2001:gg:1')
        for ip in ips:
            self.assertRaises(netaddr.core.AddrFormatError,
                              utils.get_ip_version,
                              ip)

    def test_is_valid_ip(self):
        ips = ('192.168.0.1',
               '8.8.8.8',
               'fffe::1')
        for ip in ips:
            self.assertEqual(True, utils.is_valid_ip(ip))

        # test negative cases
        ips = ('192.data.0.1',
               'text',
               None,
               '192.168.159.658')
        for ip in ips:
            self.assertEqual(False, utils.is_valid_ip(ip))

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

    def test_get_prefix_for_dns_zone(self):
        subnet_name = None
        cidr = None
        self.assertRaises(ValueError, utils.get_prefix_for_dns_zone,
                          subnet_name, cidr)

        subnet_name = "subnet 1"
        cidr = ""
        self.assertRaises(ValueError, utils.get_prefix_for_dns_zone,
                          subnet_name, cidr)

        subnet_name = "subnet 1"
        cidr = "10.10.10.10/23"
        prefix = utils.get_prefix_for_dns_zone(subnet_name, cidr)
        self.assertEqual(None, prefix)

        subnet_name = "subnet 1"
        cidr = "10.10.10.10/25"
        prefix = utils.get_prefix_for_dns_zone(subnet_name, cidr)
        self.assertEqual(subnet_name, prefix)

        subnet_name = "subnet 1"
        cidr = "fe80::8cfc:63ff:fe97:2240/64"
        prefix = utils.get_prefix_for_dns_zone(subnet_name, cidr)
        self.assertEqual(None, prefix)

    def test_get_physical_network_meta(self):
        pass

    def test_get_list_from_string(self):
        pass

    def test_exists_in_sequence(self):
        pass

    def test_exists_in_list(self):
        pass

    def test_find_one_in_list(self):
        pass

    def test_find_in_list(self):
        pass

    def test_merge_list(self):
        pass

    def test_remove_any_space(self):
        pass

    def test_get_oid_from_nios_ref(self):
        ref = None
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual(None, oid)

        ref = ""
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual(None, oid)

        ref = "networkview/ZG5zLm5ldHdvcmtfdmlldyQw:default/true"
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual("ZG5zLm5ldHdvcmtfdmlldyQw", oid)

        ref = "member:license/b25lLnByb2R1Y3RfbGljZW5zZSQwLHZuaW9zLDA:" + \
              "VNIOS/Static"
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual("b25lLnByb2R1Y3RfbGljZW5zZSQwLHZuaW9zLDA", oid)
