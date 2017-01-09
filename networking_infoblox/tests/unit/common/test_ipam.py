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

from neutron import context
from neutron.ipam import utils as ipam_utils
from neutron.tests.unit import testlib_api

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi
from networking_infoblox.tests import base


class IpamControllerTestHelper(object):

    DEFAULT_OPTIONS = {'network_name': 'test-network',
                       'external': False,
                       'shared': False,
                       'subnet_name': 'test-subnet',
                       'cidr': '11.11.1.0/24',
                       'dns_nameservers': [],
                       'enable_dhcp': True,
                       'network_view': 'test-network-view',
                       'network_view_exists': False,
                       'network_exists': False}

    def __init__(self):
        self.neutron_cxt = context.get_admin_context()
        self.tenant_id = self.neutron_cxt.tenant_id
        self.network = None
        self.subnet = None
        self.ib_cxt = mock.Mock()
        self.ib_cxt.tenant_id = self.tenant_id
        self.ib_cxt.tenant_name = 'test_tenant'
        self.ib_cxt.context = self.neutron_cxt
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.grid_config.network_template = None
        self.ib_cxt.grid_config.dhcp_relay_management_network = None
        self.ib_cxt.grid_config.wapi_version = '2.3'
        self.ib_cxt.grid_config.default_domain_name_pattern = 'int.test.com'
        self.ib_cxt.grid_config.external_domain_name_pattern = 'ext.test.com'
        self.ib_cxt.grid_config.zone_creation_strategy = []

    def prepare_test(self, options):
        self.options = self._get_options(options)

        self.network = self.create_network(self.options['network_name'],
                                           self.options['external'],
                                           self.options['shared'])

        self.subnet = self.create_subnet(self.options['subnet_name'],
                                         self.network['id'],
                                         self.options['cidr'],
                                         self.options['dns_nameservers'],
                                         self.options['enable_dhcp'])

        self.update_context(self.network,
                            self.subnet,
                            self.options['network_view'],
                            self.options['network_view_exists'])

    def _get_options(self, options):
        if not isinstance(options, dict):
            raise ValueError('Options should be passed as dict')
        for key in self.DEFAULT_OPTIONS:
            if key not in options:
                options[key] = self.DEFAULT_OPTIONS[key]
        return options

    def create_network(self, name, external=False, shared=False):
        return {
            'status': 'ACTIVE',
            'subnets': [],
            'name': name,
            'provider:physical_network': 'None',
            'router:external': external,
            'tenant_id': self.tenant_id,
            'admin_state_up': True,
            'mtu': 0,
            'shared': shared,
            'provider:network_type': 'vxlan',
            'id': str.format("{}-id", name),
            'provider:segmentation_id': 1001
        }

    def create_subnet(self, name, network_id, cidr, dns_nameservers,
                      enable_dhcp=True):
        ip_network = netaddr.IPNetwork(cidr)
        ip_range = list(ip_network)
        if ip_network.version == 6:
            raise ValueError("Test with IPv4 CIDR only")

        return {
            'name': 'subn01',
            'enable_dhcp': enable_dhcp,
            'network_id': network_id,
            'tenant_id': self.tenant_id,
            'dns_nameservers': dns_nameservers,
            'ipv6_ra_mode': 'None',
            'allocation_pools': ipam_utils.generate_pools(cidr, ip_range[1]),
            'gateway_ip': ip_range[1],
            'ipv6_address_mode': 'None',
            'ip_version': ip_network.version,
            'host_routes': [],
            'cidr': cidr,
            'id': str.format("{}-id", name),
            'subnetpool_id': 'None'
        }

    def update_context(self, network, subnet, network_view,
                       network_view_exists=False):
        self.ib_cxt.network = network
        self.ib_cxt.subnet = subnet
        self.ib_cxt.mapping.network_view = network_view
        self.ib_cxt.mapping.dns_view = 'test-view'
        if network_view_exists is False:
            self.ib_cxt.mapping.network_view_id = None
            self.ib_cxt.mapping.authority_member = None
            self.ib_cxt.mapping.dhcp_members = []
            self.ib_cxt.mapping.dns_members = []
        else:
            self.ib_cxt.mapping.network_view_id = str.format(
                "networkview/ZG5zLm5ldHdvcmtfdmlldyQw:{}/false",
                network_view)
            self.ib_cxt.mapping.authority_member = mock.Mock()
            self.ib_cxt.mapping.dhcp_members = [mock.Mock()]
            self.ib_cxt.mapping.dns_members = [mock.Mock()]


class IpamSyncControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(IpamSyncControllerTestCase, self).setUp()
        self.helper = IpamControllerTestHelper()
        self.ib_cxt = self.helper.ib_cxt
        self.grid_config = self.ib_cxt.grid_config

    def validate_network_creation(self, network_view, subnet):
        if self.ib_cxt.mapping.network_view_id:
            self.ib_cxt.ibom.create_network_view.assert_not_called()
        else:
            self.ib_cxt.reserve_authority_member.assert_called_once_with()

        self.ib_cxt.reserve_service_members.assert_called_once_with()

        self.ib_cxt.ibom.create_network.assert_called_once_with(
            network_view, subnet['cidr'], mock.ANY, mock.ANY,
            subnet['gateway_ip'], None, mock.ANY)

        allocation_pools = subnet['allocation_pools'][0]
        first_ip = netaddr.IPAddress(allocation_pools.first,
                                     subnet['ip_version']).format()
        last_ip = netaddr.IPAddress(allocation_pools.last,
                                    subnet['ip_version']).format()
        self.ib_cxt.ibom.create_ip_range.assert_called_once_with(
            network_view,
            first_ip,
            last_ip,
            subnet['cidr'],
            True,
            mock.ANY)

    @mock.patch.object(dbi, 'update_network_view_id', mock.Mock())
    @mock.patch.object(dbi, 'associate_network_view', mock.Mock())
    @mock.patch('infoblox_client.objects.Tenant')
    @mock.patch('infoblox_client.objects.IPRange')
    def test_create_subnet_new_network_view(self, ip_range_mock, tenant_mock):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ip_range_mock.search = mock.Mock(return_value=None)
        tenant = mock.Mock()
        tenant_mock.search = mock.Mock(return_value=tenant)
        with mock.patch.object(ib_objects.Network,
                               'search',
                               return_value=None):
            ipam_controller._register_mapping_member = mock.Mock()
            rollback_list = []
            ipam_controller.create_subnet(rollback_list)

        tenant_mock.search.assert_called_once_with(
            self.ib_cxt.connector, id=self.ib_cxt.tenant_id)
        tenant.update.assert_called_once_with()
        assert tenant.name == self.ib_cxt.tenant_name

        self.validate_network_creation(self.helper.options['network_view'],
                                       self.helper.subnet)

    @mock.patch.object(dbi, 'update_network_view_id', mock.Mock())
    @mock.patch.object(dbi, 'associate_network_view', mock.Mock())
    @mock.patch('infoblox_client.objects.Tenant')
    @mock.patch('infoblox_client.objects.Member')
    @mock.patch('infoblox_client.objects.IPRange')
    def test_create_subnet_existing_network_view(self, ip_range_mock,
                                                 member_mock, tenant_mock):
        test_opts = {'cidr': '12.12.12.0/24', 'network_view_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        member_mock.search = mock.Mock(return_value=None)
        ip_range_mock.search = mock.Mock(return_value=None)
        tenant = mock.Mock()
        tenant_mock.search = mock.Mock(return_value=tenant)
        with mock.patch.object(ib_objects.Network,
                               'search',
                               return_value=None):
            ipam_controller._register_mapping_member = mock.Mock()
            rollback_list = []
            ipam_controller.create_subnet(rollback_list)

        tenant_mock.search.assert_called_once_with(
            self.ib_cxt.connector, id=self.ib_cxt.tenant_id)
        tenant.update.assert_called_once_with()
        assert tenant.name == self.ib_cxt.tenant_name

        self.validate_network_creation(self.helper.options['network_view'],
                                       self.helper.subnet)

    @mock.patch.object(dbi, 'update_network_view_id', mock.Mock())
    @mock.patch.object(dbi, 'associate_network_view', mock.Mock())
    def test_create_subnet_existing_private_network(self):
        test_opts = {'network_exists': True,
                     'external': False,
                     'shared': False}
        self.helper.prepare_test(test_opts)

        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared_or_external = False
        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        with mock.patch.object(ib_objects.Network,
                               'search',
                               return_value=mock.Mock()):
            self.assertRaises(exc.InfobloxPrivateSubnetAlreadyExist,
                              ipam_controller.create_subnet,
                              [])

    @mock.patch.object(dbi, 'update_network_view_id', mock.Mock())
    @mock.patch.object(dbi, 'associate_network_view', mock.Mock())
    @mock.patch('infoblox_client.objects.Tenant')
    def test_create_subnet_existing_external_network(self, tenant_mock):
        test_opts = {'network_name': 'extnet',
                     'subnet_name': 'extsub',
                     'cidr': '172.192.1.0/24',
                     'external': True,
                     'network_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller._allocate_pools = mock.Mock()
        tenant = mock.Mock()
        tenant_mock.search = mock.Mock(return_value=tenant)
        with mock.patch.object(ib_objects.Network,
                               'search',
                               return_value=mock.Mock()):
            rollback_list = []
            ipam_controller.create_subnet(rollback_list)

        tenant_mock.search.assert_called_once_with(
            self.ib_cxt.connector, id=self.ib_cxt.tenant_id)
        tenant.update.assert_called_once_with()
        assert tenant.name == self.ib_cxt.tenant_name

        self.ib_cxt.ibom.update_network_options.assert_called_once_with(
            mock.ANY, mock.ANY)

    def test_update_subnet_allocation_pools(self):
        test_opts = {'network_exists': True,
                     'external': False,
                     'shared': False}
        self.helper.prepare_test(test_opts)
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared_or_external = False

        new_pools = (netaddr.IPRange('11.11.1.25', '11.11.1.30'),
                     netaddr.IPRange('11.11.1.45', '11.11.1.60'))
        self.ib_cxt.subnet['allocation_pools'] = new_pools
        ip_version = self.ib_cxt.subnet['ip_version']

        connector = mock.Mock()
        ib_pools = (ib_objects.IPRange(connector,
                                       start_addr='11.11.1.3',
                                       end_addr='11.11.1.19'),
                    ib_objects.IPRange(connector,
                                       start_addr='11.11.1.25',
                                       end_addr='11.11.1.30'))

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        rollback_list = []
        with mock.patch.object(ib_objects.IPRange,
                               'search_all',
                               return_value=ib_pools):
            ipam_controller.update_subnet_allocation_pools(rollback_list)

            # 1st range from ib_pools should be removed
            ib_pools[0].connector.delete_object.assert_called_once_with(None)

            # 2nd pool from new_pools should be added
            self.ib_cxt.ibom.create_ip_range.assert_called_once_with(
                self.helper.options['network_view'],
                netaddr.IPAddress(new_pools[1].first, ip_version).format(),
                netaddr.IPAddress(new_pools[1].last, ip_version).format(),
                self.helper.subnet['cidr'],
                mock.ANY, mock.ANY)

    def test_delete_subnet_for_private_network(self):
        test_opts = {'network_exists': True,
                     'external': False,
                     'shared': False}
        self.helper.prepare_test(test_opts)

        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared_or_external = False
        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller._release_service_members = mock.Mock()
        with mock.patch.object(ib_objects.Network,
                               'search_all',
                               return_value=[]):
            ipam_controller.delete_subnet()

        self.ib_cxt.ibom.delete_network.assert_called_once_with(
            self.helper.options['network_view'], self.helper.subnet['cidr'])

    def _create_ib_network_ea(self):
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
        return ib_objects.EA.from_dict(network_ea)

    def _create_ib_range_ea(self):
        range_ea = {'CMP Type': {'value': 'OpenStack'},
                    'Cloud API Owned': {'value': 'True'},
                    'Tenant ID': {'value': 'test-id'},
                    'Tenant Name': {'value': 'tenant-name'},
                    'Account': {'value': 'admin'}}
        return ib_objects.EA.from_dict(range_ea)

    def _reset_ib_range_ea(self):
        expected_ea = {'Cloud API Owned': {'value': 'False'},
                       'CMP Type': {'value': 'N/A'},
                       'Tenant ID': {'value': 'N/A'}}
        return expected_ea

    def test_delete_subnet_for_external_network_not_deletable(self):
        test_opts = {'external': True, 'network_exists': True}
        self.helper.prepare_test(test_opts)
        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller._release_service_members = mock.Mock()

        ib_network_ea = self._create_ib_network_ea()
        ib_network_mock = mock.Mock(extattrs=ib_network_ea)
        ib_range_ea = self._create_ib_range_ea()
        ib_ranges_mock = [mock.Mock(extattrs=ib_range_ea)]
        expected_ea = self._reset_ib_range_ea()

        with mock.patch.object(ib_objects.Network,
                               'search_all',
                               return_value=[]):
            with mock.patch.object(ib_objects.IPRange,
                                   'search_all',
                                   return_value=ib_ranges_mock):
                ipam_controller.delete_subnet(ib_network_mock)
                assert ib_network_mock.update.called
                assert ib_network_mock.extattrs.to_dict() == expected_ea
                assert ib_ranges_mock[0].update.called
                assert ib_ranges_mock[0].extattrs.to_dict() == expected_ea

    def test_delete_subnet_for_external_network_deletable(self):
        test_opts = {'external': True, 'network_exists': True}
        self.helper.prepare_test(test_opts)
        self.grid_config.admin_network_deletion = True

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller._release_service_members = mock.Mock()
        with mock.patch.object(ib_objects.Network,
                               'search_all',
                               return_value=[]):
            ipam_controller.delete_subnet()

        self.ib_cxt.ibom.delete_network.assert_called_once_with(
            self.helper.options['network_view'], self.helper.subnet['cidr'])

    def test_allocate_specific_ip(self):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ip_address = '11.11.1.3'
        mac = ':'.join(['00'] * 6)
        dns_view = self.ib_cxt.mapping.dns_view
        zone_auth = 'ib.com'
        hostname = mock.ANY
        ea_ip_address = mock.ANY

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.pattern_builder = mock.Mock()
        ipam_controller.pattern_builder.get_zone_name.return_value = zone_auth

        ipam_controller.allocate_specific_ip(ip_address, mac)

        ipam_controller.pattern_builder.get_zone_name.assert_called_once_with(
            is_external=self.ib_cxt.network_is_external)

        self.ib_cxt.ip_alloc.allocate_given_ip.assert_called_once_with(
            self.helper.options['network_view'], dns_view, zone_auth,
            hostname, mac, ip_address, ea_ip_address)

    def test_allocate_ip_from_pool(self):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        subnet_id = 'subnet-id'
        allocation_pools = [
            {'start': '11.11.1.1', 'end': '11.11.1.150'},
            {'start': '11.11.1.151', 'end': '11.11.1.253'}]
        mac = ':'.join(['00'] * 6)
        dns_view = self.ib_cxt.mapping.dns_view
        zone_auth = 'ib.com'
        hostname = mock.ANY
        ea_ip_address = mock.ANY

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.pattern_builder = mock.Mock()
        ipam_controller.pattern_builder.get_zone_name.return_value = zone_auth

        ipam_controller.allocate_ip_from_pool(subnet_id, allocation_pools, mac)

        ipam_controller.pattern_builder.get_zone_name.assert_called_once_with(
            is_external=self.ib_cxt.network_is_external)

        self.ib_cxt.ip_alloc.allocate_ip_from_range.assert_called_once_with(
            self.helper.options['network_view'], dns_view, zone_auth,
            hostname, mac, allocation_pools[0]['start'],
            allocation_pools[0]['end'], ea_ip_address)

    def test_deallocate_ip(self):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ip_address = '11.11.1.1'
        dns_view = self.ib_cxt.mapping.dns_view

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.deallocate_ip(ip_address)

        self.ib_cxt.ip_alloc.deallocate_ip.assert_called_once_with(
            self.helper.options['network_view'], dns_view, ip_address)


class IpamAsyncControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(IpamAsyncControllerTestCase, self).setUp()
        self.helper = IpamControllerTestHelper()
        self.ib_cxt = self.helper.ib_cxt

    def test_update_network_sync_without_subnet(self):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamAsyncController(self.ib_cxt)
        with mock.patch.object(dbi,
                               'get_subnets_by_network_id',
                               return_value=[]):
            ipam_controller.update_network_sync()
            assert not self.ib_cxt.ibom.get_network.called
            assert not self.ib_cxt.ibom.update_network_options.called

    @mock.patch.object(dbi, 'get_network_view_mappings', return_value=[])
    def test_update_network_sync_without_network_view_mapping(self, dbi_mock):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamAsyncController(self.ib_cxt)
        with mock.patch.object(dbi,
                               'get_subnets_by_network_id',
                               return_value=[{'id': 'subnet-id',
                                              'cidr': '11.11.1.0/24',
                                              'network_id': 'test_net'}]):
            ipam_controller.update_network_sync()
            assert not self.ib_cxt.ibom.get_network.called
            assert not self.ib_cxt.ibom.update_network_options.called

    @mock.patch.object(utils, 'find_one_in_list')
    @mock.patch.object(dbi, 'get_network_view_mappings')
    def test_update_network_sync_with_network_view_mapping(
            self, netview_mapping_mock, find_row_mock):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        test_netview_mapping = utils.json_to_obj(
            'NetworkViewMapping',
            {'network_view_id': 'test-id', 'network_view': 'test-view'})
        test_netview = utils.json_to_obj(
            'NetworkView',
            {'id': 'test-id', 'network_view': 'test-view'})
        netview_mapping_mock.return_value = [test_netview_mapping]
        find_row_mock.return_value = test_netview

        ipam_controller = ipam.IpamAsyncController(self.ib_cxt)
        with mock.patch.object(dbi,
                               'get_subnets_by_network_id',
                               return_value=[{'id': 'subnet-id',
                                              'cidr': '11.11.1.0/24',
                                              'network_id': 'test_net'}]):
            ipam_controller.update_network_sync()
            assert self.ib_cxt.ibom.get_network.called
            assert self.ib_cxt.ibom.update_network_options.called

    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch.object(dbi, 'get_network_view_mappings', return_value=[])
    def test_update_network_update_zone(self, dbi_mock, dns_mock):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        dns_controller = mock.Mock()
        dns_mock.return_value = dns_controller
        ipam_controller = ipam.IpamAsyncController(self.ib_cxt)
        with mock.patch.object(dbi,
                               'get_subnets_by_network_id',
                               return_value=[{'id': 'subnet-id',
                                              'cidr': '11.11.1.0/24',
                                              'network_id': 'test_net'}]):
            ipam_controller.update_network_sync()
            dns_controller.update_dns_zones.assert_called_once_with()

    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    @mock.patch('networking_infoblox.neutron.common.dns.DnsController')
    @mock.patch.object(dbi, 'get_network_view_mappings', return_value=[])
    def test_update_network_update_zone_names(self, dbi_mock, dns_mock,
                                              cxt_mock):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        dns_controller = mock.Mock()
        dns_mock.return_value = dns_controller
        ipam_controller = ipam.IpamAsyncController(self.ib_cxt)
        cxt_mock.return_value = self.ib_cxt
        with mock.patch.object(dbi,
                               'get_subnets_by_network_id',
                               return_value=[{'id': 'subnet-id',
                                              'cidr': '11.11.1.0/24',
                                              'network_id': 'test_net'}]):
            ipam_controller.update_network_sync(need_new_zones=True)
            dns_controller.update_dns_zones.assert_not_called()
            dns_controller.create_dns_zones.assert_called_once_with([])


class IpamSyncControllerUnitTestCase(base.TestCase):

    def setUp(self):
        super(IpamSyncControllerUnitTestCase, self).setUp()

    def create_restart_data(self, allow_service_restart=True):
        helper = IpamControllerTestHelper()
        ib_cxt = helper.ib_cxt
        ib_cxt.grid_config.allow_service_restart = allow_service_restart
        ib_cxt.grid_config.dhcp_support = True
        ib_cxt.ibom.restart_all_services = mock.Mock()
        ipam_controller = ipam.IpamSyncController(ib_cxt)
        member = {'name': 'member1'}
        mock.patch.object(ipam_controller, '_get_service_members',
                          return_value=[member['name']]).start()
        return ib_cxt, ipam_controller, member

    def test_restart_services_positive(self):
        (ib_cxt, ipam_controller, member) = self.create_restart_data()
        with mock.patch.object(ib_objects.Member, 'search',
                               return_value=member):
            ipam_controller._restart_services()
            ib_objects.Member.search.assert_called_once_with(
                ib_cxt.connector, host_name=member['name'],
                return_fields=['host_name'])
        ipam_controller._get_service_members.assert_called_once_with(
            'member_name')
        ib_cxt.ibom.restart_all_services.assert_called_once_with(member)

    def test_restart_services_negative(self):
        (ib_cxt, ipam_controller, member) = self.create_restart_data(False)
        with mock.patch.object(ib_objects.Member, 'search',
                               return_value=member):
            ipam_controller._restart_services()
            ib_objects.Member.search.assert_not_called()
        ipam_controller._get_service_members.assert_not_called()
        ib_cxt.ibom.restart_all_services.assert_not_called()
