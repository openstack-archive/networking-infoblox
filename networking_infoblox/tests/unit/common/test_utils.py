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

import mock
import netaddr
import six

from oslo_serialization import jsonutils

from neutron import context
from neutron.tests.unit import testlib_api

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants as const
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
        dbi.add_grid(self.ctx.session, grid_1_id, 'test grid 1', '{}', 'ON',
                     'gm-id-1')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'OFF',
                     'gm-id-2')

        grids = dbi.get_grids(self.ctx.session)
        grid_ids = utils.get_values_from_records('grid_id', grids)

        self.assertEqual(grid_1_id, grid_ids[0])
        self.assertEqual(grid_2_id, grid_ids[1])

        grid_names = utils.get_values_from_records('grid_name', grids)
        self.assertEqual('test grid 1', grid_names[0])
        self.assertEqual('test grid 2', grid_names[1])

    def test_get_composite_values_from_records(self):
        grid_1_id = 100
        grid_1_name = 'test grid 1'
        grid_2_id = 200
        grid_2_name = 'test grid 2'
        dbi.remove_grids(self.ctx.session, [grid_1_id, grid_2_id])
        dbi.add_grid(self.ctx.session, grid_1_id, grid_1_name, '{}', 'ON',
                     'gm-id-1')
        dbi.add_grid(self.ctx.session, grid_2_id, grid_2_name, '{}', 'OFF',
                     'gm-id-2')

        grids = dbi.get_grids(self.ctx.session)
        composite_keys = ['grid_id', 'grid_name']
        delimiter = '-'
        composite_values = utils.get_composite_values_from_records(
            composite_keys, grids, delimiter)
        expected_value = str(grid_1_id) + delimiter + grid_1_name
        self.assertEqual(expected_value, composite_values[0])
        expected_value = str(grid_2_id) + delimiter + grid_2_name
        self.assertEqual(expected_value, composite_values[1])

    def test_db_records_to_json(self):
        grid_1_id = 100
        grid_2_id = 200
        dbi.add_grid(self.ctx.session, grid_1_id, 'test grid 1',
                     '{"wapi_version": "2.0",'
                     '"wapi_admin_user": '
                     '{ "name": "admin", "password": "infoblox" }}',
                     'ON',
                     'gm-id-1')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'OFF',
                     'gm-id-2')

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
                     'ON',
                     'gm-id-1')
        dbi.add_grid(self.ctx.session, grid_2_id, 'test grid 2', '{}', 'ON',
                     'gm-id-2')

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
        # test EAs with scalar
        ea = {"extattrs": {"Cloud API Owned": {"value": "True"},
                           "CMP Type": {"value": "Openstack"},
                           "Subnet ID": {"value": "subnet-22222222"}}}
        cloud_api_owned_ea = utils.get_ea_value("Cloud API Owned", ea)
        self.assertEqual('True', cloud_api_owned_ea)
        cmp_type_ea = utils.get_ea_value("CMP Type", ea)
        self.assertEqual('Openstack', cmp_type_ea)
        subnet_id_ea = utils.get_ea_value("Subnet ID", ea)
        self.assertEqual('subnet-22222222', subnet_id_ea)

        # test EA with a list
        ea = {
            "extattrs": {
                "Tenant CIDR Mapping": {
                    "value": [
                        "11.11.1.0/24",
                        "11.11.2.0/24"
                    ]
                },
                "Tenant ID Mapping": {
                    "value": "1234567890"
                }
            }
        }
        tenant_cidr_mapping = utils.get_ea_value("Tenant CIDR Mapping", ea)
        expected = ["11.11.1.0/24", "11.11.2.0/24"]
        self.assertEqual(expected, tenant_cidr_mapping)
        tenant_id_mapping = utils.get_ea_value("Tenant ID Mapping", ea)
        expected = "1234567890"
        self.assertEqual(expected, tenant_id_mapping)
        # use 'should_return_list_value' parameter
        tenant_id_mapping = utils.get_ea_value("Tenant ID Mapping", ea, True)
        expected = ["1234567890"]
        self.assertEqual(expected, tenant_id_mapping)

        # negative tests
        invalid_ea = utils.get_ea_value("Invalid", ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.get_ea_value(None, ea)
        self.assertEqual(None, invalid_ea)
        invalid_ea = utils.get_ea_value(None, None)
        self.assertEqual(None, invalid_ea)

    def test_reset_required_eas(self):
        network_ea = {'CMP Type': {'value': 'OpenStack'},
                      'Cloud API Owned': {'value': 'True'},
                      'Tenant ID': {'value': 'test-id'},
                      'Tenant Name': {'value': 'tenant-name'},
                      'Account': {'value': 'admin'},
                      'Network View ID': {'value': 'default'},
                      'Is External': {'value': 'False'},
                      'Is Shared': {'value': 'True'},
                      'Network ID': {'value': 'True'},
                      'Network Name': {'value': 'True'},
                      'Subnet ID': {'value': 'True'}}
        ib_network_ea = ib_objects.EA.from_dict(network_ea)
        ib_network_mock = mock.Mock(extattrs=ib_network_ea)

        utils.reset_required_eas(ib_network_mock)

        for ea in const.REQUIRED_EA_LIST:
            ea_value = ib_network_mock.extattrs.get(ea)
            if ea == const.EA_CLOUD_API_OWNED:
                assert ea_value == 'False'
            else:
                assert ea_value == const.EA_RESET_VALUE

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

    def test_get_list_from_string(self):
        self.assertRaises(ValueError, utils.get_list_from_string, None, None)
        self.assertRaises(ValueError, utils.get_list_from_string, 'key', [])
        self.assertRaises(ValueError, utils.get_list_from_string, 'key', [''])

        test_string_list = "1,3,5,7,9"
        expected = ['1,3,5,7,9']
        actual = utils.get_list_from_string(test_string_list, [':'])
        self.assertEqual(expected, actual)
        expected = ['1', '3', '5', '7', '9']
        actual = utils.get_list_from_string(test_string_list, [','])
        self.assertEqual(expected, actual)

        test_string_list = "k1:v1, k2:v2, k3:v3"
        expected = ['k1:v1', 'k2:v2', 'k3:v3']
        actual = utils.get_list_from_string(test_string_list, [','])
        self.assertEqual(expected, actual)
        expected = [['k1', 'v1'], ['k2', 'v2'], ['k3', 'v3']]
        actual = utils.get_list_from_string(test_string_list, [',', ':'])
        self.assertEqual(expected, actual)

    def test_exists_in_sequence(self):
        self.assertRaises(ValueError, utils.exists_in_sequence, None, None)
        self.assertRaises(ValueError, utils.exists_in_sequence, 'key', None)
        self.assertEqual(False, utils.exists_in_sequence([], []))

        search_list = [1, 2, 3, 4, 'a', 'b', 'c']

        actual = utils.exists_in_sequence([], search_list)
        self.assertEqual(False, actual)

        actual = utils.exists_in_sequence([1, 5], search_list)
        self.assertEqual(False, actual)

        actual = utils.exists_in_sequence([1, 2, 4], search_list)
        self.assertEqual(False, actual)

        actual = utils.exists_in_sequence([4, 'a', 'b'], search_list)
        self.assertEqual(True, actual)

    def test_exists_in_list(self):
        self.assertRaises(ValueError, utils.exists_in_list, None, None)
        self.assertRaises(ValueError, utils.exists_in_list, 'key', None)
        self.assertEqual(False, utils.exists_in_list([], []))

        search_list = [1, 2, 3, 4, 'a', 'b', 'c']

        actual = utils.exists_in_list([], search_list)
        self.assertEqual(False, actual)

        actual = utils.exists_in_list([1, 5], search_list)
        self.assertEqual(False, actual)

        actual = utils.exists_in_list([1, 'a'], search_list)
        self.assertEqual(True, actual)

        actual = utils.exists_in_list([1, 4, 'c'], search_list)
        self.assertEqual(True, actual)

    def test_find_one_in_list(self):
        self.assertRaises(ValueError, utils.find_one_in_list, None, None, None)
        self.assertEqual(None, utils.find_one_in_list('key', None, []))
        self.assertEqual(None, utils.find_one_in_list('key', 'val', []))

        search_list = [{'key1': 'val1', 'key2': 'val2', 'key3': True},
                       {'key1': 'val11', 'key2': 'val22', 'key3': False}]

        expected = None
        actual = utils.find_one_in_list('key2', 'val33', search_list)
        self.assertEqual(expected, actual)

        expected = {'key1': 'val11', 'key2': 'val22', 'key3': False}
        actual = utils.find_one_in_list('key2', 'val22', search_list)
        self.assertEqual(expected, actual)

    def test_find_in_list_by_condition(self):
        self.assertRaises(ValueError,
                          utils.find_in_list_by_condition, None, None)
        self.assertRaises(ValueError,
                          utils.find_in_list_by_condition, 'key', [])
        self.assertEqual(None,
                         utils.find_in_list_by_condition({'key': 'val'}, []))

        search_list = [{'key1': 'val1', 'key2': 'val2', 'key3': 'val3'},
                       {'key1': 'val11', 'key2': 'val22', 'key3': 'val33'},
                       {'key1': 'val1', 'key2': 'val2', 'key3': 'val333'}]

        search_condition = {'key2': 'val33'}
        expected = []
        actual = utils.find_in_list_by_condition(search_condition, search_list)
        self.assertEqual(expected, actual)

        search_condition = {'key2': 'val22'}
        expected = {'key1': 'val11', 'key2': 'val22', 'key3': 'val33'}
        actual = utils.find_in_list_by_condition(search_condition, search_list)
        self.assertEqual(expected, actual[0])

        search_condition = {'key1': 'val1', 'key3': 'val3'}
        expected = {'key1': 'val1', 'key2': 'val2', 'key3': 'val3'}
        actual = utils.find_in_list_by_condition(search_condition, search_list)
        self.assertEqual(expected, actual[0])

        search_condition = {'key1': 'val1', 'key2': 'val2'}
        expected = [{'key1': 'val1', 'key2': 'val2', 'key3': 'val3'},
                    {'key1': 'val1', 'key2': 'val2', 'key3': 'val333'}]
        actual = utils.find_in_list_by_condition(search_condition, search_list)
        self.assertEqual(expected, actual)

    def test_find_in_list(self):
        self.assertRaises(ValueError, utils.find_in_list, None, None, None)
        self.assertRaises(ValueError, utils.find_in_list, 'key', 'val', [])
        self.assertEqual(None, utils.find_in_list('key', ['val'], []))

        key = 'key'
        value = ['val1']
        search_list = [{'key': 'val'}]
        self.assertEqual([], utils.find_in_list(key, value, search_list))

        key = 'key'
        value = ['val1']
        search_list = [{'key': 'val1'}]
        expected = [{'key': 'val1'}]
        self.assertEqual(expected, utils.find_in_list(key, value, search_list))

        key = 'key'
        value = ['val1', 'val3']
        search_list = [{'key': 'val1'},
                       {'key': 'val2'},
                       {'key': 'val3'}]
        expected = [{'key': 'val1'}, {'key': 'val3'}]
        self.assertEqual(expected, utils.find_in_list(key, value, search_list))

    def test_find_key_from_list(self):
        self.assertRaises(ValueError, utils.find_key_from_list, None, None)
        self.assertRaises(ValueError, utils.find_key_from_list, 'ley', {})
        self.assertEqual(None, utils.find_key_from_list('key', []))
        self.assertEqual([], utils.find_key_from_list('key', ['val']))

        key = 'key1'
        search_list = [{'key': 'val'}]
        self.assertEqual([], utils.find_key_from_list(key, search_list))

        key = 'key'
        search_list = [{'key': 'val1'}]
        expected = [{'key': 'val1'}]
        self.assertEqual(expected, utils.find_key_from_list(key, search_list))

        key = 'key'
        search_list = [{'key': 'val1'},
                       {'key': 'val2'},
                       {'key2': 'val3'}]
        expected = [{'key': 'val1'}, {'key': 'val2'}]
        self.assertEqual(expected, utils.find_key_from_list(key, search_list))

    def test_merge_list(self):
        self.assertRaises(ValueError, utils.merge_list, None)
        self.assertRaises(ValueError, utils.merge_list, [], "string")
        self.assertEqual([], utils.merge_list([]))
        self.assertEqual([], utils.merge_list([], []))
        self.assertEqual([1], utils.merge_list([1], [1]))
        self.assertEqual([1, 2, 3, 4, 5],
                         utils.merge_list([1, 2, 3], [1, 4, 5]))
        self.assertEqual([1, 2, 3, 4, 5, 6],
                         utils.merge_list([1, 2, 3], [1, 4, 5], [6]))
        self.assertEqual(set(['a', 'b', 'c', 'd']),
                         set(utils.merge_list(['a', 'b'], ['a', 'c'], ['d'])))

    def test_remove_any_space(self):
        self.assertEqual('', utils.remove_any_space(''))
        self.assertEqual('', utils.remove_any_space('   '))
        self.assertEqual(None, utils.remove_any_space(None))
        self.assertEqual('add', utils.remove_any_space('\nadd'))
        self.assertEqual('abcde', utils.remove_any_space(' ab cd  \ne '))

    def test_get_hash(self):
        hash_str = utils.get_hash("")
        self.assertEqual(32, len(hash_str))

        hash_str = utils.get_hash(None)
        self.assertEqual(32, len(hash_str))

        hash_str = utils.get_hash([])
        self.assertEqual(32, len(hash_str))

        hash_str = utils.get_hash()
        self.assertEqual(32, len(hash_str))

        hash_str = utils.get_hash(['abc'])
        self.assertEqual(32, len(hash_str))

        hash_str = utils.get_hash('I need a hash string!!!')
        self.assertEqual(32, len(hash_str))

    def test_get_oid_from_nios_ref(self):
        ref = None
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual(None, oid)

        ref = ""
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual(None, oid)

        ref = 123344
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual(None, oid)

        ref = "networkview/ZG5zLm5ldHdvcmtfdmlldyQw:default/true"
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual("ZG5zLm5ldHdvcmtfdmlldyQw", oid)

        ref = "member:license/b25lLnByb2R1Y3RfbGljZW5zZSQwLHZuaW9zLDA:" + \
              "VNIOS/Static"
        oid = utils.get_oid_from_nios_ref(ref)
        self.assertEqual("b25lLnByb2R1Y3RfbGljZW5zZSQwLHZuaW9zLDA", oid)

    def test_get_network_info_from_nios_ref(self):
        ref = None
        network = utils.get_network_info_from_nios_ref(ref)
        self.assertEqual(None, network)

        ref = ""
        network = utils.get_network_info_from_nios_ref(ref)
        self.assertEqual(None, network)

        ref = "network/ZG5zLm5ldHdvcmskMTQuMTQuMS4wLzI0LzQ:" + \
              "14.14.1.0/24/hs-view-4"
        network = utils.get_network_info_from_nios_ref(ref)
        expect = {'object_id': 'ZG5zLm5ldHdvcmskMTQuMTQuMS4wLzI0LzQ',
                  'network_view': 'hs-view-4',
                  'cidr': '14.14.1.0/24'}
        self.assertEqual(expect, network)

        ref = "ipv6network/ZG5zLm5ldHdvcmskMjAwMTpkYjg6ODVhMzo6LzY0LzA:" + \
              "2001%3Adb8%3A85a3%3A%3A/64/default"
        network = utils.get_network_info_from_nios_ref(ref)
        expect = {'object_id': 'ZG5zLm5ldHdvcmskMjAwMTpkYjg6ODVhMzo6LzY0LzA',
                  'network_view': 'default',
                  'cidr': '2001:db8:85a3::/64'}
        self.assertEqual(expect, network)

    def test_get_member_status(self):
        self.assertEqual(const.MEMBER_STATUS_OFF,
                         utils.get_member_status(None))

        self.assertEqual(const.MEMBER_STATUS_OFF,
                         utils.get_member_status('babo'))

        status = const.MEMBER_NODE_STATUS_FAILED
        self.assertEqual(const.MEMBER_STATUS_OFF,
                         utils.get_member_status(status))

        status = const.MEMBER_NODE_STATUS_INACTIVE
        self.assertEqual(const.MEMBER_STATUS_OFF,
                         utils.get_member_status(status))

        status = const.MEMBER_NODE_STATUS_WARNING
        self.assertEqual(const.MEMBER_STATUS_ON,
                         utils.get_member_status(status))

        status = const.MEMBER_NODE_STATUS_WORKING
        self.assertEqual(const.MEMBER_STATUS_ON,
                         utils.get_member_status(status))

    def test_get_notification_handler_name(self):
        event_type = 'network.create.start'
        expected = 'create_network_alert'
        self.assertEqual(expected,
                         utils.get_notification_handler_name(event_type))

        event_type = 'network.create.end'
        expected = 'create_network_sync'
        self.assertEqual(expected,
                         utils.get_notification_handler_name(event_type))

        event_type = 'floatingip.delete.end'
        expected = 'delete_floatingip_sync'
        self.assertEqual(expected,
                         utils.get_notification_handler_name(event_type))

        event_type = 'compute.instance.create.end'
        expected = 'create_instance_sync'
        self.assertEqual(expected,
                         utils.get_notification_handler_name(event_type))

    def test_generate_network_view_name(self):
        self.assertRaises(ValueError, utils.generate_network_view_name, None)
        self.assertRaises(ValueError, utils.generate_network_view_name, [])
        self.assertRaises(ValueError, utils.generate_network_view_name, '')
        self.assertRaises(ValueError, utils.generate_network_view_name, '', '')
        self.assertRaises(ValueError, utils.generate_network_view_name, '5', 8)
        self.assertEqual('123', utils.generate_network_view_name('123', []))
        self.assertEqual('1234', utils.generate_network_view_name('1234', ''))
        self.assertEqual('1234', utils.generate_network_view_name('1234'))
        self.assertEqual('hi-23', utils.generate_network_view_name('23', 'hi'))

    def test_generate_network_view_name_max_len(self):
        name = 'tempest-NetworksTest'
        id = '279909910-24625c5053c7483ab6273628423989'
        netview_name = utils.generate_network_view_name(id, name)
        self.assertEqual(const.NETVIEW_MAX_LEN, len(netview_name))
        expected_name = '-'.join([name, id])[:const.NETVIEW_MAX_LEN]
        self.assertEqual(expected_name, netview_name)

    def test_get_ipv4_network_prefix(self):
        self.assertEqual(None,
                         utils.get_ipv4_network_prefix('2001:db8:85a3::/64',
                                                       ''))
        self.assertEqual(None,
                         utils.get_ipv4_network_prefix('11.11.1.1/24', ''))
        self.assertEqual(None,
                         utils.get_ipv4_network_prefix('11.11.1.1/24', ''))
        self.assertEqual('11-11-1-1-25',
                         utils.get_ipv4_network_prefix('11.11.1.1/25', ''))
        self.assertEqual('sub1',
                         utils.get_ipv4_network_prefix('11.11.1.1/25', 'sub1'))
        self.assertEqual('11-11-1-1-29',
                         utils.get_ipv4_network_prefix('11.11.1.1/29', None))

    def test_get_dhcp_member_ips_from_network_json(self):
        network_json = {
            "members": [
                {
                    "_struct": "dhcpmember",
                    "ipv4addr": "192.168.1.10",
                    "ipv6addr": None,
                    "name": "nios-7.2.0-member3.com"
                }
            ]
        }
        member_ips = utils.get_dhcp_member_ips(network_json)
        self.assertEqual("192.168.1.10", member_ips[0])

    def test_get_dhcp_member_ips_from_ib_network(self):
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='test-view',
                                               cidr='12.12.1.0/24')
        test_ib_network.members = [
            ib_objects.AnyMember(_struct='dhcpmember',
                                 name='nios-7.2.0-member3.com',
                                 ipv4addr='192.168.1.10')]

        member_ips = utils.get_dhcp_member_ips(test_ib_network)
        self.assertEqual("192.168.1.10", member_ips[0])

    def test_get_dns_member_ips_from_network_json(self):
        network_json = {
            "options": [
                {
                    "name": "domain-name-servers",
                    "num": 6,
                    "use_option": True,
                    "value": "192.168.1.10,192.168.1.13",
                    "vendor_class": "DHCP"
                }
            ]
        }
        member_ips = utils.get_dns_member_ips(network_json)
        self.assertEqual("192.168.1.10", member_ips[0])
        self.assertEqual("192.168.1.13", member_ips[1])

    def test_get_dns_member_ips_from_ib_network(self):
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='test-view',
                                               cidr='12.12.1.0/24')
        test_ib_network.options = [
            ib_objects.DhcpOption(name='domain-name-servers',
                                  value='192.168.1.10,192.168.1.13')]
        member_ips = utils.get_dns_member_ips(test_ib_network)
        self.assertEqual("192.168.1.10", member_ips[0])
        self.assertEqual("192.168.1.13", member_ips[1])

    def test_get_router_ips_from_network_json(self):
        network_json = {
            "options": [
                {
                    "name": "routers",
                    "num": 3,
                    "use_option": True,
                    "value": "192.168.1.1,192.168.1.2",
                    "vendor_class": "DHCP"
                }
            ]
        }
        member_ips = utils.get_router_ips(network_json)
        self.assertEqual("192.168.1.1", member_ips[0])
        self.assertEqual("192.168.1.2", member_ips[1])

    def test_get_router_ips_from_ib_network(self):
        connector = mock.Mock()
        test_ib_network = ib_objects.NetworkV4(connector,
                                               network_view='test-view',
                                               cidr='12.12.1.0/24')
        test_ib_network.options = [
            ib_objects.DhcpOption(name='routers',
                                  value='192.168.1.1,192.168.1.2')]
        member_ips = utils.get_router_ips(test_ib_network)
        self.assertEqual("192.168.1.1", member_ips[0])
        self.assertEqual("192.168.1.2", member_ips[1])

    def test_find_member_by_ip_from_list(self):
        self.assertRaises(ValueError,
                          utils.find_member_by_ip_from_list, None, None)
        self.assertRaises(ValueError,
                          utils.find_member_by_ip_from_list, None, [])
        self.assertRaises(netaddr.core.AddrFormatError,
                          utils.find_member_by_ip_from_list, '1.0.1.555', [])
        self.assertEqual(None,
                         utils.find_member_by_ip_from_list('11.1.1.1', []))

        search_list = [{'member_ip': '11.1.1.1', 'member_ipv6': '2001::1'},
                       {'member_ip': '11.1.1.2', 'member_ipv6': None}]

        search_ip = '11.1.1.2'
        actual = utils.find_member_by_ip_from_list(search_ip, search_list)
        self.assertEqual(search_ip, actual['member_ip'])

        search_ip = '2001::1'
        actual = utils.find_member_by_ip_from_list(search_ip, search_list)
        self.assertEqual(search_ip, actual['member_ipv6'])

    def test_get_nameservers_raises_exception(self):
        self.assertRaises(ValueError, utils.get_nameservers, None, None)
        self.assertRaises(ValueError, utils.get_nameservers, [], None)
        self.assertRaises(ValueError, utils.get_nameservers, [], 5)

    def _test_get_nameservers(self, dns_members, expected_field, ip_version):
        nameservers = utils.get_nameservers(dns_members, ip_version)
        expected = [getattr(m, expected_field) for m in dns_members]
        self.assertEqual(expected, nameservers)

    def test_get_nameservers(self):
        test_dhcp_member_1 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'REGULAR',
             'member_ip': '11.11.1.12', 'member_ipv6': '2001::1',
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_dns_ip': None, 'member_dns_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON'})
        test_dhcp_member_2 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'CPM',
             'member_ip': '11.11.1.13', 'member_ipv6': '2001::2',
             'member_dhcp_ip': None, 'member_dhcp_ipv6': None,
             'member_dns_ip': None, 'member_dns_ipv6': None,
             'member_name': 'm1', 'member_status': 'ON'})
        dns_members = [test_dhcp_member_1, test_dhcp_member_2]

        self._test_get_nameservers(dns_members, 'member_ip', 4)
        self._test_get_nameservers(dns_members, 'member_ipv6', 6)

    def test_get_nameservers_dns_fields(self):
        test_dhcp_member_1 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'REGULAR',
             'member_ip': '11.11.1.12', 'member_ipv6': '2001::1',
             'member_dhcp_ip': '12.12.1.12', 'member_dhcp_ipv6': '2009::1',
             'member_dns_ip': '15.10.1.2', 'member_dns_ipv6': '2016::1',
             'member_name': 'm1', 'member_status': 'ON'})
        test_dhcp_member_2 = utils.json_to_obj(
            'DhcpMember',
            {'member_id': 'member-id', 'member_type': 'CPM',
             'member_ip': '11.11.1.13', 'member_ipv6': '2001::2',
             'member_dhcp_ip': '12.12.1.13', 'member_dhcp_ipv6': '2009::2',
             'member_dns_ip': '15.10.1.3', 'member_dns_ipv6': '2016::2',
             'member_name': 'm1', 'member_status': 'ON'})
        dns_members = [test_dhcp_member_1, test_dhcp_member_2]

        self._test_get_nameservers(dns_members, 'member_dns_ip', 4)
        self._test_get_nameservers(dns_members, 'member_dns_ipv6', 6)

    def test_get_features(self):
        feature = utils.get_features('2.3')
        self.assertTrue(feature.create_ea_def)
        self.assertTrue(feature.cloud_api)
        self.assertTrue(feature.member_ipv6_setting)
        self.assertTrue(feature.member_licenses)
        self.assertTrue(feature.enable_member_dns)
        self.assertTrue(feature.enable_member_dhcp)
        self.assertTrue(feature.dns_settings)
        self.assertTrue(feature.enable_dhcp)
        self.assertTrue(feature.tenants)
