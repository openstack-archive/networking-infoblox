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

from neutron_lib import constants as n_const

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import pattern

from networking_infoblox.tests import base


class TestPatternBuilder(base.TestCase):

    def setUp(self):
        super(TestPatternBuilder, self).setUp()
        self.ib_cxt = self._get_ib_context()
        self.pattern_builder = pattern.PatternBuilder(self.ib_cxt)
        self.test_ip = '11.11.11.11'
        self.expected_ip = self.test_ip.replace('.', '-').replace(':', '-')
        self.expected_domain = (
            self.ib_cxt.grid_config.default_domain_name_pattern.replace(
                '{subnet_id}', self.ib_cxt.subnet['id'])
        )

    def _get_ib_context(self):
        ib_cxt = mock.Mock()
        ib_cxt.network = {'id': 'network-id',
                          'name': 'test-net-1',
                          'tenant_id': 'network-id'}
        ib_cxt.subnet = {'id': 'subnet-id',
                         'name': 'test-sub-1',
                         'tenant_id': 'tenant-id',
                         'network_id': 'network-id'}
        ib_cxt.grid_config.default_host_name_pattern = 'host-{ip_address}'
        ib_cxt.grid_config.default_domain_name_pattern = (
            '{subnet_id}.infoblox.com')
        ib_cxt.grid_config.external_host_name_pattern = ''
        ib_cxt.grid_config.external_domain_name_pattern = ''
        return ib_cxt

    def _get_test_port(self, device_owner):
        return {'id': 'port-id',
                'name': 'port-name',
                'device_owner': device_owner,
                'port_id': 'port-id',
                'device_id': 'device-id'}

    def _test_get_hostname(self, expected_hostname,
                           device_owner=n_const.DEVICE_OWNER_FLOATINGIP,
                           instance_name='test-vm',
                           external=False,):
        test_port = self._get_test_port(device_owner)
        actual_hostname = self.pattern_builder.get_hostname(
            self.test_ip, instance_name, test_port['id'],
            test_port['device_owner'], test_port['device_id'],
            external=external)
        self.assertEqual(expected_hostname, actual_hostname)

    def test_get_hostname_for_floating_ip_with_instance_name(self):
        expected_hostname = str.format("floating-ip-{}.{}", self.expected_ip,
                                       self.expected_domain)
        self._test_get_hostname(expected_hostname, external=True)

    def test_get_hostname_for_floating_ip_without_instance_name(self):
        instance_name = None
        expected_hostname = str.format("floating-ip-{}.{}", self.expected_ip,
                                       self.expected_domain)
        self._test_get_hostname(expected_hostname,
                                instance_name=instance_name,
                                external=True)

    def test_get_hostname_for_floating_ip_with_instance_name_pattern(self):
        instance_name = 'test-vm'
        self.pattern_builder.grid_config.default_host_name_pattern = (
            'host-{instance_name}')
        expected_hostname = str.format("host-{}.{}", instance_name,
                                       self.expected_domain)
        self._test_get_hostname(expected_hostname,
                                instance_name=instance_name,
                                external=True)

    def test_get_hostname_for_floating_ip_external_pattern(self):
        self.pattern_builder.grid_config.external_host_name_pattern = (
            '{instance_name}')
        self.pattern_builder.grid_config.external_domain_name_pattern = (
            'external.infoblox.com')
        instance_name = 'test-vm'
        expected_hostname = '.'.join([
            instance_name,
            self.pattern_builder.grid_config.external_domain_name_pattern])
        self._test_get_hostname(expected_hostname,
                                instance_name=instance_name,
                                external=True)

    def test_get_hostname_for_other_device_owners(self):
        for dev, patt in const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP.items():
            expected_hostname = str.format(
                "{}.{}", patt.replace('{ip_address}',
                                      self.expected_ip),
                self.expected_domain)
            self._test_get_hostname(expected_hostname,
                                    device_owner=dev,
                                    instance_name='')

    def test_get_hostname_for_other_device_owners_external(self):
        self.pattern_builder.grid_config.external_host_name_pattern = (
            '{instance_name}')
        self.pattern_builder.grid_config.external_domain_name_pattern = (
            'external.infoblox.com')
        for dev, patt in const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP.items():
            expected_hostname = str.format(
                "{}.{}", patt.replace('{ip_address}',
                                      self.expected_ip),
                self.pattern_builder.grid_config.external_domain_name_pattern)
            self._test_get_hostname(expected_hostname,
                                    device_owner=dev,
                                    instance_name='',
                                    external=True)

    def test_get_hostname_for_instance_name(self):
        test_port = self._get_test_port('')
        self.pattern_builder.grid_config.default_host_name_pattern = (
            'host-{instance_name}')

        instance_name = 'test.vm'
        actual_hostname = self.pattern_builder.get_hostname(
            self.test_ip, instance_name, test_port['id'],
            test_port['device_owner'], test_port['device_id'])
        expected_instance_name = (
            instance_name.replace('.', '-').replace(':', '-'))
        expected_hostname = str.format("host-{}.{}", expected_instance_name,
                                       self.expected_domain)
        self.assertEqual(expected_hostname, actual_hostname)

    def test_get_hostname_for_port_name(self):
        test_port = self._get_test_port('')
        self.pattern_builder.grid_config.default_host_name_pattern = (
            'host-{port_name}')

        # test hostname with port_name
        actual_hostname = self.pattern_builder.get_hostname(
            self.test_ip, None, test_port['id'], test_port['device_owner'],
            test_port['device_id'], test_port['name'])
        expected_hostname = str.format("host-{}.{}", test_port['name'],
                                       self.expected_domain)
        self.assertEqual(expected_hostname, actual_hostname)

        # test hostname without port_name but with ip
        actual_hostname = self.pattern_builder.get_hostname(
            self.test_ip, None, test_port['id'], test_port['device_owner'],
            test_port['device_id'])
        ip_addr = self.test_ip.replace('.', '-').replace(':', '-')
        expected_hostname = str.format("host-{}.{}", ip_addr,
                                       self.expected_domain)
        self.assertEqual(expected_hostname, actual_hostname)

        # test hostname without port_name and ip
        actual_hostname = self.pattern_builder.get_hostname(
            None, None, test_port['id'], test_port['device_owner'],
            test_port['device_id'])
        expected_hostname = str.format("host-{}.{}", test_port['id'],
                                       self.expected_domain)
        self.assertEqual(expected_hostname, actual_hostname)

    def test_get_zone_name(self):
        # test {subnet_id} pattern
        actual_zone = self.pattern_builder.get_zone_name()
        self.assertEqual(self.expected_domain, actual_zone)

        # test {network_name} pattern
        self.pattern_builder.grid_config.default_domain_name_pattern = (
            '{network_name}.infoblox.com')
        self.expected_domain = (
            self.ib_cxt.grid_config.default_domain_name_pattern.replace(
                '{network_name}', self.ib_cxt.network['name'])
        )
        actual_zone = self.pattern_builder.get_zone_name()
        self.assertEqual(self.expected_domain, actual_zone)

        # test static zone name
        zone = 'infoblox.com'
        self.pattern_builder.grid_config.default_domain_name_pattern = zone
        actual_zone = self.pattern_builder.get_zone_name()
        self.assertEqual(zone, actual_zone)

    def test_get_zone_name_for_external_patern_not_set(self):
        actual_zone = self.pattern_builder.get_zone_name(is_external=True)
        # default pattern should be used if external is not set
        self.assertEqual(self.expected_domain, actual_zone)

    def test_get_zone_name_for_external_patern_set(self):
        external_pattern = 'external.infoblox.com'
        self.pattern_builder.grid_config.external_domain_name_pattern = (
            external_pattern)
        actual_zone = self.pattern_builder.get_zone_name(is_external=True)
        # external pattern should be used
        self.assertEqual(external_pattern, actual_zone)

    def test_get_zone_name_pattern(self):
        # test get_zone_name pattern
        self.assertEqual(
            self.pattern_builder.get_zone_name_pattern(is_external=False),
            self.ib_cxt.grid_config.default_domain_name_pattern)

    def test_get_zone_name_pattern_for_external(self):
        # test get_zone_name pattern for external zone
        self.pattern_builder.grid_config.external_domain_name_pattern = (
            'external.infoblox.com')
        self.assertEqual(
            self.pattern_builder.get_zone_name_pattern(is_external=True),
            self.ib_cxt.grid_config.external_domain_name_pattern)
