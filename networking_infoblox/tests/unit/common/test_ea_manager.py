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

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import ea_manager
from networking_infoblox.tests import base


class EaManagerTestCase(base.TestCase):

    def setUp(self):
        super(EaManagerTestCase, self).setUp()
        self.user_id = mock.Mock()
        self.tenant_id = mock.Mock()

    def test_get_common_ea_for_network(self):
        network = {'router:external': True,
                   'shared': True}
        expected_ea = {'Is External': True,
                       'Is Shared': True,
                       'Cloud API Owned': False,
                       'Tenant ID': self.tenant_id,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(network,
                                                self.user_id,
                                                self.tenant_id,
                                                for_network=True)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea(self):
        network = {'router:external': True,
                   'shared': True}
        expected_ea = {'Cloud API Owned': False,
                       'Tenant ID': self.tenant_id,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(network,
                                                self.user_id,
                                                self.tenant_id)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_no_network(self):
        expected_ea = {'Is External': False,
                       'Is Shared': False,
                       'Cloud API Owned': True,
                       'Tenant ID': self.tenant_id,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(None,
                                                self.user_id,
                                                self.tenant_id,
                                                for_network=True)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_cloud_api_owned_true(self):
        owned_true = ({'router:external': False,
                       'shared': False},
                      None,
                      {})
        for network in owned_true:
            generated_ea = ea_manager.get_common_ea(network, None, None)
            self.assertEqual(True, generated_ea['Cloud API Owned'])

    def test_get_common_ea_cloud_api_owned_false(self):
        owned_false = ({'router:external': True,
                        'shared': False},
                       {'router:external': False,
                        'shared': True},
                       {'router:external': True,
                        'shared': True})
        for network in owned_false:
            generated_ea = ea_manager.get_common_ea(network, None, None)
            self.assertEqual(False, generated_ea['Cloud API Owned'])

    def test_get_ea_for_network_view(self):
        ea = ea_manager.get_ea_for_network_view(self.tenant_id)
        self.assertEqual(self.tenant_id, ea.get('Tenant ID'))
        self.assertEqual(False, ea.get('Cloud API Owned'))

    def test_get_ea_for_network(self):
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
                   'Tenant ID': self.tenant_id,
                   'Account': self.user_id,
                   'Is External': True,
                   'Is Shared': True,
                   'Cloud API Owned': False}
        ea = ea_manager.get_ea_for_network(self.user_id, self.tenant_id,
                                           network, subnet)
        for key, value in mapping.items():
            self.assertEqual(mapping[key], ea.get(key))

    def test_get_ea_for_range(self):
        network = {'router:external': False,
                   'shared': False}
        ea = ea_manager.get_ea_for_range(self.user_id, self.tenant_id, network)
        self.assertIsInstance(ea, ib_objects.EA)
        self.assertEqual(True, ea.get('Cloud API Owned'))
        self.assertEqual(self.tenant_id, ea.get('Tenant ID'))
        self.assertEqual(self.user_id, ea.get('Account'))

    def test_get_default_ea_for_ip(self):
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Account': self.user_id,
                       'Port ID': None,
                       'Port Attached Device - Device Owner': None,
                       'Port Attached Device - Device ID': None,
                       'Cloud API Owned': True,
                       'IP Type': 'Fixed',
                       'VM ID': None}
        ea = ea_manager.get_default_ea_for_ip(self.user_id, self.tenant_id)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip(self):
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = mock.Mock()
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': True,
                       'IP Type': 'Fixed',
                       'VM ID': device_id}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id, network,
                                      port_id, device_id, device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_floatingip(self):
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = mock.Mock()
        instance_id = mock.Mock()
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': True,
                       'IP Type': 'Floating',
                       'VM ID': instance_id}
        ea = ea_manager.get_ea_for_floatingip(self.user_id, self.tenant_id,
                                              network, port_id, device_id,
                                              device_owner, instance_id)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_zone(self):
        network = {'router:external': False,
                   'shared': False}
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Account': self.user_id,
                       'Cloud API Owned': True}
        ea = ea_manager.get_ea_for_zone(self.user_id, self.tenant_id, network)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))
