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

from infoblox_client import exceptions as ib_exc
from neutron import context
from neutron.ipam import utils as ipam_utils
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit import testlib_api
from oslo_config import cfg

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
        self.grid_mgr._report_sync_time = mock.Mock()
        self.grid_mgr.mapping._sync_nios_for_network_view = mock.Mock()
        self.grid_mgr.member._discover_dns_settings = mock.Mock(
            return_value={})
        self.grid_mgr.member._discover_dhcp_settings = mock.Mock(
            return_value={})
        self.grid_mgr.sync()
        self.grid_mgr.get_config = mock.Mock()

    def _setup_config(self):
        cfg.CONF.set_override('core_plugin',
                              'neutron.plugins.ml2.plugin.Ml2Plugin')
        ml2_config.cfg.CONF.set_override('type_drivers', 'local', group='ml2')

    def _mock_subnet(self, subnet_pool, requested_pools, cidr, gateway):
        ip_version = 4
        subnetpool_id = subnet_pool['id]'] if subnet_pool else None
        # if pools is passed, then allocation_pools should be a request format
        # which is IPRange type, but if not passed, then subnet format is
        # subnet dict.
        if requested_pools is None:
            requested_pools = ipam_utils.generate_pools(cidr, gateway)
            allocation_pools = [
                {'start': str(netaddr.IPAddress(p.first, ip_version)),
                 'end': str(netaddr.IPAddress(p.last, ip_version))}
                for p in requested_pools]
        else:
            allocation_pools = requested_pools

        return {
            'id': 'subnet-id',
            'cidr': cidr,
            'tenant_id': 'tenant-id',
            'gateway_ip': gateway,
            'name': 'subnet-name',
            'network_id': 'network-id',
            'subnetpool_id': subnetpool_id,
            'allocation_pools': allocation_pools,
            'ip_version': ip_version,
            'enable_dhcp': True}

    @mock.patch.object(grid, 'GridManager', mock.Mock())
    def _mock_driver(self, subnet_pool=None, requested_pools=None,
                     cidr='192.168.10.0/24', gateway='192.168.10.1'):
        driver = drv.InfobloxPool(subnet_pool, self.ctx)
        driver._grid_manager = self.grid_mgr

        driver._subnetpool = subnet_pool if subnet_pool else None
        subnet = self._mock_subnet(subnet_pool, requested_pools, cidr, gateway)
        driver._fetch_subnet = mock.Mock(return_value=subnet)
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
        driver = self._mock_driver(requested_pools=pools)
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
        driver = self._mock_driver(requested_pools=pools)
        driver._grid_config.default_domain_name_pattern = (
            '{subnet_id}.cloud.global.com')
        driver._get_ib_network = mock.Mock(return_value=mock.Mock())
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
        driver = self._mock_driver(requested_pools=pools)
        subnet_factory = driver.get_subnet_request_factory()
        driver._grid_config.default_domain_name_pattern = (
            '{subnet_name}.cloud.global.com')
        driver._get_ib_network = mock.Mock(return_value=mock.Mock())
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

    def _mock_port(self, device_owner=None):
        return {'id': 'port-id',
                'name': 'port-name',
                'mac_address': 'mac-address',
                'tenant_id': 'tenant-id',
                'device_id': 'device-id',
                'device_owner': device_owner}

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_allocate_specific_ip(self, ib_cxt_mock, ipam_mock, dns_mock):
        driver = self._mock_driver()
        subnet_id = 'subnet-id'
        ipam_subnet = driver.get_subnet(subnet_id)

        port = self._mock_port()
        expected_ip = {'ip_address': '192.168.1.15'}
        address_factory = driver.get_address_request_factory()
        address_request = address_factory.get_request(self.ctx,
                                                      port,
                                                      expected_ip)

        ipam_subnet.allocate(address_request)

        ipam_mock.IpamSyncController.allocate_specific_ip.called_once_with(
            expected_ip['ip_address'],
            port['mac_address'],
            port['id'],
            port['tenant_id'],
            port['device_id'],
            port['device_owner'])
        dns_mock.DnsController.bind_names.called_once_with(
            expected_ip['ip_address'],
            None,
            port['id'],
            port['tenant_id'],
            port['device_id'],
            port['device_owner'])

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_allocate_ip_from_pool(self, ib_cxt_mock, ipam_mock, dns_mock):
        driver = self._mock_driver()
        subnet_id = 'subnet-id'
        ipam_subnet = driver.get_subnet(subnet_id)

        port = self._mock_port()
        address_factory = driver.get_address_request_factory()
        address_request = address_factory.get_request(self.ctx,
                                                      port,
                                                      {})

        allocated_ip = ipam_subnet.allocate(address_request)

        ipam_mock.IpamSyncController.allocate_ip_from_pool.called_once_with(
            ipam_subnet._neutron_subnet['id'],
            ipam_subnet._neutron_subnet['allocation_pools'],
            port['mac_address'],
            port['id'],
            port['tenant_id'],
            port['device_id'],
            port['device_owner'])
        dns_mock.DnsController.bind_names.called_once_with(
            allocated_ip,
            None,
            port['id'],
            port['tenant_id'],
            port['device_id'],
            port['device_owner'])

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch('networking_infoblox.neutron.common.ipam.IpamSyncController')
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    @mock.patch('infoblox_client.objects.FixedAddress')
    def test_deallocate_ip(self, fixed_ip_mock, ib_cxt_mock, ipam_mock,
                           dns_mock):
        driver = self._mock_driver()
        subnet_id = 'subnet-id'
        ipam_subnet = driver.get_subnet(subnet_id)

        expected_ip = {'ip_address': '192.168.1.15'}

        port = self._mock_port()
        address_factory = driver.get_address_request_factory()
        address_request = address_factory.get_request(self.ctx,
                                                      port,
                                                      expected_ip)

        fixed_address_mock = mock.Mock()
        fixed_ip_mock.search = mock.Mock(return_value=fixed_address_mock)
        ipam_subnet._build_address_request_from_ib_address = mock.Mock(
            return_value=address_request)

        ipam_subnet.deallocate(netaddr.IPAddress(expected_ip['ip_address']))

        ipam_mock.IpamSyncController.deallocate_ip.called_once_with(
            expected_ip['ip_address'])
        dns_mock.DnsController.unbind_names.called_once_with(
            expected_ip['ip_address'],
            None,
            port['id'],
            port['tenant_id'],
            port['device_id'],
            port['device_owner'])


class FakePool(object):

    def __init__(self, object_mock):
        self.mock = object_mock

    @drv.rollback_wrapper
    def allocate_something(self, rollback_list, fail=False):
        rollback_list.append(self.mock)
        if fail:
            raise ValueError


class TestWrapper(base.TestCase):

    def test_rollback_wrapper(self):
        created_object = mock.Mock()
        pool = FakePool(created_object)
        pool.allocate_something()
        self.assertEqual(False, created_object.delete.called)

    def test_rollback_wrapper_on_failure(self):
        created_object = mock.Mock()
        pool = FakePool(created_object)
        self.assertRaises(ValueError, pool.allocate_something, fail=True)
        self.assertEqual(True, created_object.delete.called)

    def test_rollback_wrapper_on_delete_failure(self):
        created_object = mock.Mock()
        created_object.delete.side_effect = ib_exc.InfobloxException(
            'error_response')
        pool = FakePool(created_object)
        self.assertRaises(ValueError, pool.allocate_something, fail=True)
        self.assertEqual(True, created_object.delete.called)
