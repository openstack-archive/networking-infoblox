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

from infoblox_client import objects

from networking_infoblox.neutron.common import ea_manager
from networking_infoblox.tests import base


class EaManagerTestCase(base.TestCase):

    def test_get_common_ea(self):
        network = {'router:external': True,
                   'shared': True}
        expected_ea = {'Is External': True,
                       'Is Shared': True,
                       'Cloud API Owned': False}
        generated_ea = ea_manager.get_common_ea(network)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_no_network(self):
        expected_ea = {'Is External': False,
                       'Is Shared': False,
                       'Cloud API Owned': True}
        generated_ea = ea_manager.get_common_ea(None)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_cloud_api_owned_true(self):
        owned_true = ({'router:external': False,
                       'shared': False},
                      None,
                      {})
        for network in owned_true:
            generated_ea = ea_manager.get_common_ea(network)
            self.assertEqual(True, generated_ea['Cloud API Owned'])

    def test_get_common_ea_cloud_api_owned_false(self):
        owned_false = ({'router:external': True,
                        'shared': False},
                       {'router:external': False,
                        'shared': True},
                       {'router:external': True,
                        'shared': True})
        for network in owned_false:
            generated_ea = ea_manager.get_common_ea(network)
            self.assertEqual(False, generated_ea['Cloud API Owned'])

    def test_get_ea_for_network_view(self):
        tenant_id = mock.Mock()
        ea = ea_manager.get_ea_for_network_view(tenant_id)
        self.assertEqual(tenant_id, ea.get('Tenant ID'))
        self.assertEqual(False, ea.get('Cloud API Owned'))

    def test_get_ea_for_network(self):
        user_id = mock.Mock()
        tenant_id = mock.Mock()
        network = {'id': mock.Mock(),
                   'name': mock.Mock(),
                   'provider:network_type': mock.Mock(),
                   'provider:physical_network': mock.Mock(),
                   'provider:segmentation_id': mock.Mock(),
                   'router:external': True,
                   'shared': True}
        subnet = {'id': mock.Mock(),
                  'name': mock.Mock()}
        mapping = {'Subnet ID': subnet['id'],
                   'Subnet Name': subnet['name'],
                   'Network ID': network['id'],
                   'Network Name': network['name'],
                   'Network Encap': network['provider:network_type'],
                   'Segmentation ID': network['provider:segmentation_id'],
                   'Physical Network Name': (
                       network['provider:physical_network']),
                   'Tenant ID': tenant_id,
                   'Account': user_id,
                   'Is External': True,
                   'Is Shared': True,
                   'Cloud API Owned': False}
        ea = ea_manager.get_ea_for_network(user_id, tenant_id,
                                           network, subnet)
        for key, value in mapping.items():
            self.assertEqual(mapping[key], ea.get(key))

    def test_get_ea_for_range(self):
        user_id = mock.Mock()
        tenant_id = mock.Mock()
        network = {'router:external': False,
                   'shared': False}
        ea = ea_manager.get_ea_for_range(user_id, tenant_id, network)
        self.assertIsInstance(ea, objects.EA)
        self.assertEqual(True, ea.get('Cloud API Owned'))
        self.assertEqual(tenant_id, ea.get('Tenant ID'))
        self.assertEqual(user_id, ea.get('Account'))

    def test_get_default_ea_for_ip(self):
        tenant_id = mock.Mock()
        user_id = mock.Mock()
        expected_ea = {'Tenant ID': tenant_id,
                       'Account': user_id,
                       'Port ID': None,
                       'Port Attached Device - Device Owner': None,
                       'Port Attached Device - Device ID': None,
                       'Cloud API Owned': True,
                       'IP Type': 'Fixed',
                       'VM ID': None}
        ea = ea_manager.get_default_ea_for_ip(user_id, tenant_id)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip(self):
        tenant_id = mock.Mock()
        user_id = mock.Mock()
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = mock.Mock()
        expected_ea = {'Tenant ID': tenant_id,
                       'Account': user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': True,
                       'IP Type': 'Fixed',
                       'VM ID': device_id}

        ea = ea_manager.get_ea_for_ip(user_id, tenant_id, network, port_id,
                                      device_id, device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_floatingip(self):
        tenant_id = mock.Mock()
        user_id = mock.Mock()
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = mock.Mock()
        expected_ea = {'Tenant ID': tenant_id,
                       'Account': user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': True,
                       'IP Type': 'Floating',
                       'VM ID': None}
        ea = ea_manager.get_ea_for_floatingip(user_id, tenant_id, network,
                                              port_id, device_id,
                                              device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_zone(self):
        tenant_id = mock.Mock()
        user_id = mock.Mock()
        network = {'router:external': False,
                   'shared': False}
        expected_ea = {'Tenant ID': tenant_id,
                       'Account': user_id,
                       'Cloud API Owned': True}
        ea = ea_manager.get_ea_for_zone(user_id, tenant_id, network)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))
