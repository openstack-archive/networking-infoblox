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
import netaddr

from neutron.ipam import requests

from networking_infoblox.neutron.ipam import driver as drv
from networking_infoblox.tests import base


class TestDriver(base.TestCase):

    def test_driver_initialized(self):
        self.assertIsInstance(drv.InfobloxPool(mock.Mock(), mock.Mock()),
                              drv.InfobloxPool)

    def _mock_driver(self, subnet_pool=None, cidr='192.168.10.0/24',
                     gateway='192.168.10.1'):
       driver = drv.InfobloxPool(subnet_pool, mock.Mock())
       driver._get_connector = mock.Mock(return_value='connector')
       driver._fetch_subnet = mock.Mock(return_value={
            'id': 'subnet-id',
            'cidr': cidr,
            'tenant_id': 'tenant-id',
            'gateway_ip': '192.168.10.1'})
       return driver

    @mock.patch('infoblox_client.objects.Network')
    def test_get_subnet(self, net):
        driver = self._mock_driver()
        
        ipam_subnet = driver.get_subnet(mock.Mock())

        self.assertTrue(driver._get_connector.called)
        net.search.assert_called_with('connector',
                                      network_view='default',
                                      network='192.168.10.0/24')

        self.assertIsInstance(ipam_subnet, drv.InfobloxSubnet)

    @mock.patch('infoblox_client.objects.Network')
    def test_allocate_subnet(self, net):
        driver = self._mock_driver(None)
        pools = [netaddr.ip.IPRange('192.168.10.3', '192.168.10.25')]

        request = requests.SpecificSubnetRequest(
            'tenant_id', 'subnet_id', '192.168.10.0/24',
            '192.168.10.1', pools)
        ipam_subnet = driver.allocate_subnet(request)
        self.assertIsInstance(ipam_subnet, drv.InfobloxSubnet)

    @mock.patch('infoblox_client.objects.Network')
    def test_remove_subnet(self, net):
        nios_net = mock.Mock()
        net.search = mock.Mock(return_value=nios_net)
        driver = self._mock_driver()

        ipam_subnet = driver.remove_subnet('subnet-id')

        self.assertTrue(driver._get_connector.called)
        net.search.assert_called_with('connector',
                                      network_view='default',
                                      network='192.168.10.0/24')

        nios_net.delete.assert_called_with('connector')

    @mock.patch('infoblox_client.connector.Connector')
    def test_get_connector(self, conn_mock):
        expected_opts = {'host': '',
                         'username': '',
                         'password': '',
                         'wapi_version': '',
                         'ssl_verify': False,
                         'http_pool_connections': 100,
                         'http_pool_maxsize': 100,
                         'http_request_timeout': 120}
        conn_mock._parse_options = mock.Mock()
        connector = drv.InfobloxPool._get_connector()
        self.assertIsInstance(connector, conn.Connector)
        conn_mock.assert_called_with(expected_opts)

