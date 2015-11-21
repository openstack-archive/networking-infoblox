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
from oslo_config import cfg

from neutron import context
from neutron.ipam import requests
from neutron.ipam import utils as ipam_utils
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit import testlib_api

from networking_infoblox.ipam import driver as drv
from networking_infoblox.neutron.common import grid
from networking_infoblox.tests import base
from networking_infoblox.tests.unit import grid_sync_stub


class TestDriver(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(TestDriver, self).setUp()
        self.ctx = context.get_admin_context()
        self._setup_config()
        self.grid_stub = grid_sync_stub.GridSyncStub(self.ctx,
                                                     self.connector_fixture)
        self.grid_stub.prepare_grid_manager(wapi_version='2.0')
        self.grid_mgr = self.grid_stub.get_grid_manager()
        self.grid_mgr.sync()
        self.grid_mgr.get_config = mock.Mock()

    def _setup_config(self):
        cfg.CONF.set_override('core_plugin',
                              'neutron.plugins.ml2.plugin.Ml2Plugin')
        ml2_config.cfg.CONF.set_override('type_drivers', 'local', group='ml2')

    @mock.patch.object(grid, 'GridManager', mock.Mock())
    def _mock_driver(self, subnet_pool=None, request_pools=None,
                     cidr='192.168.10.0/24', gateway='192.168.10.1'):
        ip_version = 4
        driver = drv.InfobloxPool(subnet_pool, self.ctx)
        driver._grid_manager = self.grid_mgr

        driver._subnetpool = subnet_pool if subnet_pool else None
        subnetpool_id = subnet_pool['id]'] if subnet_pool else None

        # if pools is passed, then allocation_pools should be a request format
        # which is IPRange type, but if not passed, then subnet format is
        # subnet dict.
        if request_pools is None:
            request_pools = ipam_utils.generate_pools(cidr, gateway)
            allocation_pools = [
                {'start': str(netaddr.IPAddress(p.first, ip_version)),
                 'end': str(netaddr.IPAddress(p.last, ip_version))}
                for p in request_pools]
        else:
            allocation_pools = request_pools

        driver._fetch_subnet = mock.Mock(return_value={
            'id': 'subnet-id',
            'cidr': cidr,
            'tenant_id': 'tenant-id',
            'gateway_ip': gateway,
            'name': 'subnet-name',
            'network_id': 'network-id',
            'subnetpool_id': subnetpool_id,
            'allocation_pools': allocation_pools,
            'ip_version': ip_version,
            'enable_dhcp': True})
        return driver

    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_get_subnet(self, ib_cxt_mock, ipam_mock):
        driver = self._mock_driver()
        subnet_id = 'subnet-id'
        ipam_subnet = driver.get_subnet(subnet_id)

        ipam_mock.IpamSyncController.get_subnet.called_once_with()
        self.assertIsInstance(ipam_subnet, drv.InfobloxSubnet)

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_allocate_subnet(self, ib_cxt_mock, ipam_mock, dns_mock):
        pools = [netaddr.ip.IPRange('192.168.10.3', '192.168.10.25')]
        driver = self._mock_driver(request_pools=pools)
        subnet_factory = driver.get_subnet_request_factory()
        subnet_request = subnet_factory.get_request(self.ctx,
                                                    driver._fetch_subnet(),
                                                    None)

        ipam_subnet = driver.allocate_subnet(subnet_request)

        ipam_mock.IpamSyncController.create_subnet.called_once_with()
        dns_mock.DnsController.create_dns_zones.called_once_with()
        self.assertIsInstance(ipam_subnet, drv.InfobloxSubnet)

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_update_subnet_no_zone_change(self, ib_cxt_mock, ipam_mock,
                                          dns_mock):
        pools = [netaddr.ip.IPRange('192.168.10.3', '192.168.10.25')]
        driver = self._mock_driver(request_pools=pools)
        driver._grid_config.default_domain_name_pattern = (
            '{subnet_id}.cloud.global.com')
        subnet_factory = driver.get_subnet_request_factory()
        subnet_request = subnet_factory.get_request(self.ctx,
                                                    driver._fetch_subnet(),
                                                    None)

        driver.update_subnet(subnet_request)

        ipam_mock.IpamSyncController.update_subnet_allocation_pools.\
            called_once_with()
        assert not ipam_mock.IpamSyncController.create_dns_zones.called
        ipam_mock.IpamSyncController.get_subnet.called_once_with()
        ipam_mock.IpamSyncController.update_subnet_eas.called_once_with()

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_update_subnet_zone_change(self, ib_cxt_mock, ipam_mock, dns_mock):
        pools = [netaddr.ip.IPRange('192.168.10.3', '192.168.10.25')]
        driver = self._mock_driver(request_pools=pools)
        subnet_factory = driver.get_subnet_request_factory()
        driver._grid_config.default_domain_name_pattern = (
            '{subnet_name}.cloud.global.com')
        test_subnet = driver._fetch_subnet()
        test_subnet['name'] = 'subnet-name-new'
        subnet_request = subnet_factory.get_request(self.ctx,
                                                    test_subnet,
                                                    None)

        driver.update_subnet(subnet_request)

        ipam_mock.IpamSyncController.update_subnet_allocation_pools.\
            called_once_with()
        ipam_mock.IpamSyncController.create_dns_zones.called_once_with()
        dns_mock.DnsController.create_dns_zones.called_once_with()
        ipam_mock.IpamSyncController.update_subnet_eas.called_once_with()

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_remove_subnet(self, ib_cxt_mock, ipam_mock, dns_mock):
        driver = self._mock_driver()
        subnet_id = 'subnet-id'
        driver._get_ib_network = mock.Mock(return_value=mock.Mock())

        driver.remove_subnet(subnet_id)

        ipam_mock.IpamSyncController.delete_subnet.called_once_with()
        dns_mock.DnsController.delete_dns_zones.called_once_with()

    def _mock_subnet(self, cidr='192.168.1.0/24', pools=None):
        subnet_req = requests.SpecificSubnetRequest(
            'tenant_id', 'subnet_id', cidr, pools)
        infoblox_network = mock.Mock()
        infoblox_network.network = cidr
        return drv.InfobloxSubnet(subnet_req, infoblox_network)

    @mock.patch('infoblox_client.connector.Connector')
    @mock.patch('networking_infoblox.ipam.driver.InfobloxPool')
    @mock.patch('infoblox_client.objects.FixedAddress')
    def test_allocate_static_ip(self, fa, driver, connector):
        ipam_sub = self._mock_subnet()
        expected_ip = '192.168.1.15'
        fixed_address_mock = mock.Mock()
        fixed_address_mock.ip = expected_ip
        fa.create = mock.Mock(return_value=fixed_address_mock)

        address_req = requests.SpecificAddressRequest(expected_ip)
        allocated_ip = ipam_sub.allocate(address_req)

        fa.create.assert_called_with(connector(),
                                     network_view='default',
                                     ip=expected_ip,
                                     mac='00:00:00:00:00:00',
                                     check_if_exists=False)
        self.assertEqual(expected_ip, allocated_ip)

    @mock.patch('infoblox_client.objects.IPAllocation')
    @mock.patch('infoblox_client.objects.IPRange')
    @mock.patch('infoblox_client.connector.Connector')
    @mock.patch('networking_infoblox.ipam.driver.InfobloxPool')
    @mock.patch('infoblox_client.objects.FixedAddress')
    def test_allocate_ip_from_range(self, fa, driver, connector, range_mock,
                                    ip_alloc):
        ipam_sub = self._mock_subnet()
        nios_range = mock.Mock()
        nios_range.start_addr = '192.168.1.15'
        nios_range.end_addr = '192.168.1.35'
        range_mock.search_all.return_value = [nios_range]

        address_req = requests.AnyAddressRequest()
        allocated_ip = ipam_sub.allocate(address_req)

        range_mock.search_all.assert_called_with(connector(),
                                                 network_view='default',
                                                 network='192.168.1.0/24')
        ip_alloc.next_available_ip_from_range.assert_called_with(
            'default',
            nios_range.start_addr,
            nios_range.end_addr)
        fa.create.assert_called_with(connector(),
                                     network_view='default',
                                     ip=mock.ANY,
                                     mac='00:00:00:00:00:00',
                                     check_if_exists=False)
        self.assertEqual(fa.create().ip, allocated_ip)

    @mock.patch('infoblox_client.connector.Connector')
    @mock.patch('networking_infoblox.ipam.driver.InfobloxPool')
    @mock.patch('infoblox_client.objects.FixedAddress')
    def test_deallocate_ip(self, fa, driver, connector):
        ipam_sub = self._mock_subnet()
        expected_ip = '192.168.1.15'
        fixed_address_mock = mock.Mock()
        fa.search = mock.Mock(return_value=fixed_address_mock)

        ipam_sub.deallocate(expected_ip)

        fa.search.assert_called_with(connector(),
                                     network_view='default',
                                     ip=expected_ip)
        fixed_address_mock.delete.assert_called_with()
