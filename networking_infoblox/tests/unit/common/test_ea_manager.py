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

from neutron.common import constants as n_const

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import ea_manager
from networking_infoblox.tests import base


class EaManagerTestCase(base.TestCase):

    def setUp(self):
        super(EaManagerTestCase, self).setUp()
        self.grid_id = 100
        self.user_id = mock.Mock()
        self.tenant_id = 'Tenant ID'
        self.tenant_name = 'Tenant Name'
        self.context = mock.Mock()
        self.context.tenant_id = self.tenant_id
        self.context.tenant_name = self.tenant_name

    def test_get_common_ea_for_network(self):
        network = {'router:external': True,
                   'shared': True}
        expected_ea = {'Is External': 'True',
                       'Is Shared': 'True',
                       'CMP Type': 'OpenStack',
                       'Cloud API Owned': 'False',
                       'Tenant ID': self.tenant_id,
                       'Tenant Name': self.tenant_name,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(network,
                                                self.user_id,
                                                self.tenant_id,
                                                self.tenant_name,
                                                for_network=True)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea(self):
        network = {'router:external': 'True',
                   'shared': 'True'}
        expected_ea = {'CMP Type': 'OpenStack',
                       'Cloud API Owned': 'False',
                       'Tenant ID': self.tenant_id,
                       'Tenant Name': self.tenant_name,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(network,
                                                self.user_id,
                                                self.tenant_id,
                                                self.tenant_name)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_no_network(self):
        expected_ea = {'Is External': 'False',
                       'Is Shared': 'False',
                       'CMP Type': 'OpenStack',
                       'Cloud API Owned': 'True',
                       'Tenant ID': self.tenant_id,
                       'Tenant Name': self.tenant_name,
                       'Account': self.user_id}
        generated_ea = ea_manager.get_common_ea(None,
                                                self.user_id,
                                                self.tenant_id,
                                                self.tenant_name,
                                                for_network=True)
        self.assertEqual(expected_ea, generated_ea)

    def test_get_common_ea_cloud_api_owned_true(self):
        owned_true = ({'router:external': False,
                       'shared': False},
                      None,
                      {})
        for network in owned_true:
            generated_ea = ea_manager.get_common_ea(network, None, None, None)
            self.assertEqual(str(True), generated_ea['Cloud API Owned'])

    def test_get_common_ea_cloud_api_owned_false(self):
        owned_false = ({'router:external': True,
                        'shared': False},
                       {'router:external': False,
                        'shared': True},
                       {'router:external': True,
                        'shared': True})
        for network in owned_false:
            generated_ea = ea_manager.get_common_ea(network, None, None, None)
            self.assertEqual(str(False), generated_ea['Cloud API Owned'])

    def test_get_ea_for_network_view(self):
        ea = ea_manager.get_ea_for_network_view(self.tenant_id,
                                                self.tenant_name,
                                                self.grid_id)
        self.assertEqual(self.tenant_id, ea.get('Tenant ID'))
        self.assertEqual(self.tenant_name, ea.get('Tenant Name'))
        self.assertEqual(str(False), ea.get('Cloud API Owned'))
        self.assertEqual('100', ea.get('Cloud Adapter ID'))
        self.assertEqual('OpenStack', ea.get('CMP Type'))

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
                   'Tenant Name': self.tenant_name,
                   'Account': self.user_id,
                   'Is External': str(True),
                   'Is Shared': str(True),
                   'Cloud API Owned': str(False)}
        ea = ea_manager.get_ea_for_network(self.user_id, self.tenant_id,
                                           self.tenant_name, network, subnet)
        for key, value in mapping.items():
            self.assertEqual(mapping[key], ea.get(key))

    def test_get_ea_for_range(self):
        network = {'router:external': False,
                   'shared': False}
        ea = ea_manager.get_ea_for_range(self.user_id, self.tenant_id,
                                         self.tenant_name, network)
        self.assertIsInstance(ea, ib_objects.EA)
        self.assertEqual(str(True), ea.get('Cloud API Owned'))
        self.assertEqual(self.tenant_id, ea.get('Tenant ID'))
        self.assertEqual(self.tenant_name, ea.get('Tenant Name'))
        self.assertEqual(self.user_id, ea.get('Account'))

    def test_get_default_ea_for_ip(self):
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': None,
                       'Port Attached Device - Device Owner': None,
                       'Port Attached Device - Device ID': None,
                       'Cloud API Owned': str(True),
                       'IP Type': 'Fixed',
                       'VM ID': None}
        ea = ea_manager.get_default_ea_for_ip(self.user_id, self.tenant_id,
                                              self.tenant_name)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip(self):
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = mock.Mock()
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': str(True),
                       'IP Type': 'Fixed',
                       'VM ID': None}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id,
                                      self.tenant_name, network,
                                      port_id, device_id, device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip_with_router_gateway_ip(self):
        network = {'router:external': False,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = n_const.DEVICE_OWNER_ROUTER_GW
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': str(True),
                       'IP Type': 'Fixed',
                       'VM ID': None}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id,
                                      self.tenant_name, network,
                                      port_id, device_id, device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip_with_floatingip_creation(self):
        network = {'router:external': True,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = n_const.DEVICE_OWNER_FLOATINGIP
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': str(False),
                       'IP Type': 'Floating',
                       'VM ID': None}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id,
                                      self.tenant_name, network, port_id,
                                      device_id, device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip_with_floatingip_association(self):
        network = {'router:external': True,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = const.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA
        is_floating_ip = True
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': str(False),
                       'IP Type': 'Floating',
                       'VM ID': device_id}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id,
                                      self.tenant_name,
                                      network, port_id, device_id,
                                      device_owner, is_floating_ip)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_ip_with_floatingip_dissociation(self):
        network = {'router:external': True,
                   'shared': False}
        port_id = mock.Mock()
        device_id = mock.Mock()
        device_owner = n_const.DEVICE_OWNER_FLOATINGIP
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'Port ID': port_id,
                       'Port Attached Device - Device Owner': device_owner,
                       'Port Attached Device - Device ID': device_id,
                       'Cloud API Owned': str(False),
                       'IP Type': 'Floating',
                       'VM ID': None}

        ea = ea_manager.get_ea_for_ip(self.user_id, self.tenant_id,
                                      self.tenant_name,
                                      network, port_id, device_id,
                                      device_owner)
        for key, value in expected_ea.items():
            self.assertEqual(value, ea.get(key))

    def test_get_ea_for_zones_without_net(self):
        # Test that None values is acceptable for network/subnet parameters
        expected_ea = {'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'CMP Type': 'OpenStack',
                       'Cloud API Owned': str(True)}
        ea = ea_manager.get_ea_for_reverse_zone(self.user_id, self.tenant_id,
                                                self.tenant_name, None, None)
        self.assertEqual(expected_ea, ea.ea_dict)
        ea = ea_manager.get_ea_for_forward_zone(self.user_id, self.tenant_id,
                                                self.tenant_name, None, None,
                                                '{subnet_id}.infoblox.com')
        self.assertEqual(expected_ea, ea.ea_dict)

    def test_get_ea_for_reverse_zone(self):
        network = {'id': mock.Mock(),
                   'name': mock.Mock(),
                   'provider:segmentation_id': mock.Mock(),
                   'provider:physical_network': mock.Mock(),
                   'provider:network_type': mock.Mock()}
        subnet = {'id': mock.Mock(),
                  'name': mock.Mock()}
        expected_ea = {'Subnet ID': subnet['id'],
                       'Subnet Name': subnet['name'],
                       'Network ID': network['id'],
                       'Network Name': network['name'],
                       'Network Encap': network['provider:network_type'],
                       'Segmentation ID': network['provider:segmentation_id'],
                       'Physical Network Name': (
                           network['provider:physical_network']),
                       'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'CMP Type': 'OpenStack',
                       'Cloud API Owned': str(True)}
        ea = ea_manager.get_ea_for_reverse_zone(self.user_id, self.tenant_id,
                                                self.tenant_name, network,
                                                subnet)
        self.assertEqual(expected_ea, ea.ea_dict)

    def _test_get_ea_for_forward_zone(self, template, skip_eas):
        network = {'id': mock.Mock(),
                   'name': mock.Mock(),
                   'provider:segmentation_id': mock.Mock(),
                   'provider:physical_network': mock.Mock(),
                   'provider:network_type': mock.Mock()}
        subnet = {'id': mock.Mock(),
                  'name': mock.Mock()}
        verified_ea = {'Subnet ID': subnet['id'],
                       'Subnet Name': subnet['name'],
                       'Network ID': network['id'],
                       'Network Name': network['name'],
                       'Network Encap': network['provider:network_type'],
                       'Segmentation ID': network['provider:segmentation_id'],
                       'Physical Network Name': (
                           network['provider:physical_network']),
                       'Tenant ID': self.tenant_id,
                       'Tenant Name': self.context.tenant_name,
                       'Account': self.user_id,
                       'CMP Type': 'OpenStack',
                       'Cloud API Owned': str(True)}
        ea = ea_manager.get_ea_for_forward_zone(self.user_id, self.tenant_id,
                                                self.tenant_name, network,
                                                subnet, template)
        expected_ea = {key: value for key, value in verified_ea.items()
                       if key not in skip_eas}
        self.assertEqual(expected_ea, ea.ea_dict)

    def test_get_ea_for_forward_zone_template_subnet(self):
        self._test_get_ea_for_forward_zone(template='{subnet_id}',
                                           skip_eas=())
        self._test_get_ea_for_forward_zone(template='{subnet_name}',
                                           skip_eas=())

    def test_get_ea_for_forward_zone_template_network(self):
        skip_eas = ('Subnet ID', 'Subnet Name')
        self._test_get_ea_for_forward_zone(template='{network_id}',
                                           skip_eas=skip_eas)
        self._test_get_ea_for_forward_zone(template='{network_name}',
                                           skip_eas=skip_eas)

    def test_get_ea_for_forward_zone_no_net_in_template(self):
        skip_eas = ('Subnet ID', 'Subnet Name', 'Network ID', 'Network Name',
                    'Network Encap', 'Segmentation ID',
                    'Physical Network Name')
        self._test_get_ea_for_forward_zone(
            template='private.infoblox.com', skip_eas=skip_eas)

    def test_reset_ea_for_network(self):
        network_ea = {'CMP Type': {'value': 'OpenStack'},
                      'Cloud API Owned': {'value': 'True'},
                      'Tenant ID': {'value': 'test-id'},
                      'Tenant Name': {'value': 'tenant-name'},
                      'Account': {'value': 'admin'},
                      'Is External': {'value': 'False'},
                      'Is Shared': {'value': 'True'},
                      'Network ID': {'value': 'True'},
                      'Network Name': {'value': 'True'},
                      'Subnet ID': {'value': 'True'},
                      'Subnet Name': {'value': 'True'},
                      'Network Encap': {'value': 'gre'},
                      'Segmentation ID': {'value': 'segmentation-id'},
                      'Physical Network Name': {'value': 'physical-network'}}
        ib_network_ea = ib_objects.EA.from_dict(network_ea)
        ib_network_mock = mock.Mock(extattrs=ib_network_ea)

        ea_manager.reset_ea_for_network(ib_network_mock)

        expected_ea = {'Cloud API Owned': {'value': 'N/A'},
                       'CMP Type': {'value': 'N/A'},
                       'Tenant ID': {'value': 'N/A'}}
        ib_network_mock.extattrs.ea_dict == expected_ea

    def test_reset_ea_for_range(self):
        range_ea = {'CMP Type': {'value': 'OpenStack'},
                    'Cloud API Owned': {'value': 'True'},
                    'Tenant ID': {'value': 'test-id'},
                    'Tenant Name': {'value': 'tenant-name'},
                    'Account': {'value': 'admin'}}
        ib_range_ea = ib_objects.EA.from_dict(range_ea)
        ib_range_mock = mock.Mock(extattrs=ib_range_ea)

        ea_manager.reset_ea_for_range(ib_range_mock)

        expected_ea = {'Cloud API Owned': {'value': 'N/A'},
                       'CMP Type': {'value': 'N/A'},
                       'Tenant ID': {'value': 'N/A'}}
        ib_range_mock.extattrs.ea_dict == expected_ea

    def test_reset_ea_for_zone(self):
        zone_ea = {'CMP Type': {'value': 'OpenStack'},
                   'Cloud API Owned': {'value': 'True'},
                   'Tenant ID': {'value': 'test-id'},
                   'Tenant Name': {'value': 'tenant-name'},
                   'Account': {'value': 'admin'}}
        ib_zone_ea = ib_objects.EA.from_dict(zone_ea)
        ib_zone_mock = mock.Mock(extattrs=ib_zone_ea)

        ea_manager.reset_ea_for_zone(ib_zone_mock)

        expected_ea = {'Cloud API Owned': {'value': 'N/A'},
                       'CMP Type': {'value': 'N/A'},
                       'Tenant ID': {'value': 'N/A'}}
        ib_zone_mock.extattrs.ea_dict == expected_ea
