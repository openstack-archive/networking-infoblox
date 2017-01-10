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
from neutron_lib import constants as n_const

from networking_infoblox.ipam import requests
from networking_infoblox.tests import base


class TestDriver(base.TestCase):

    def _get_mocked_port(self, device_owner=None, mac=None):
        if device_owner is None:
            device_owner = mock.Mock()
        if mac is None:
            mac = mock.Mock()
        return {'mac_address': mac,
                'tenant_id': mock.Mock(),
                'id': mock.Mock(),
                'device_id': mock.Mock(),
                'device_owner': device_owner}

    def _validate_ib_fields_in_request(self, port, request):
        self.assertEqual(port['mac_address'], request.mac)
        self.assertEqual(port['id'], request.port_id)
        self.assertEqual(port['device_id'], request.device_id)
        self.assertEqual(port['device_owner'], request.device_owner)

    def _test_static_requests(self, device_owner, request_class):
        context = mock.Mock()
        port = self._get_mocked_port(device_owner=device_owner)
        ip_dict = {'ip_address': '192.168.1.10',
                   'subnet_id': mock.Mock()}
        req = requests.InfobloxAddressRequestFactoryV2.get_request(context,
                                                                   port,
                                                                   ip_dict)
        self.assertIsInstance(req, request_class)
        self.assertEqual(req.address,
                         netaddr.IPAddress(ip_dict['ip_address']))
        self._validate_ib_fields_in_request(port, req)

    def test_fixed_address_request(self):
        self._test_static_requests(mock.Mock(),
                                   requests.InfobloxFixedAddressRequest)

    def test_floating_address_request(self):
        self._test_static_requests(n_const.DEVICE_OWNER_FLOATINGIP,
                                   requests.InfobloxFloatingAddressRequest)

    def test_router_gateway_address_request(self):
        self._test_static_requests(
            n_const.DEVICE_OWNER_ROUTER_GW,
            requests.InfobloxRouterGatewayAddressRequest)

    def test_dhcp_port_address_request(self):
        self._test_static_requests(
            n_const.DEVICE_OWNER_DHCP,
            requests.InfobloxDhcpPortAddressRequest)

    def test_any_address_request(self):
        context = mock.Mock()
        port = self._get_mocked_port()
        ip_dict = {}
        req = requests.InfobloxAddressRequestFactoryV2.get_request(context,
                                                                   port,
                                                                   ip_dict)
        self.assertIsInstance(req, requests.InfobloxAnyAddressRequest)
        self._validate_ib_fields_in_request(port, req)

    def test_auto_address_request(self):
        context = mock.Mock()
        mac = 'aa:ab:dc:11:22:33'
        port = self._get_mocked_port(mac=mac)
        ip_dict = {'eui64_address': True,
                   'subnet_cidr': 'fffe::/64',
                   'mac': mac}
        req = requests.InfobloxAddressRequestFactoryV2.get_request(context,
                                                                   port,
                                                                   ip_dict)
        self.assertIsInstance(req, requests.InfobloxAutomaticAddressRequest)
        self.assertEqual(req.address,
                         netaddr.IPAddress('fffe::a8ab:dcff:fe11:2233'))
        self._validate_ib_fields_in_request(port, req)
