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
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import ipam
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
        self.tenant_id = 'tenant-id'
        self.network = None
        self.subnet = None
        self.ib_cxt = mock.Mock()
        self.ib_cxt.context = self.neutron_cxt
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.grid_config.network_template = None
        self.ib_cxt.grid_config.dhcp_replay_management_network = None
        self.ib_cxt.ibom.network_exists.return_value = False

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

        if self.options['network_exists']:
            self.ib_cxt.ibom.network_exists.return_value = True

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
            'id': str.format("%s-id", name),
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
            'allocation_pools': [{'start': ip_range[2],
                                  'end': ip_range[-2]}],
            'gateway_ip': ip_range[1],
            'ipv6_address_mode': 'None',
            'ip_version': ip_network.version,
            'host_routes': [],
            'cidr': cidr,
            'id': str.format("%s-id", name),
            'subnetpool_id': 'None'
        }

    def update_context(self, network, subnet, network_view,
                       network_view_exists=False):
        self.ib_cxt.network = network
        self.ib_cxt.subnet = subnet
        self.ib_cxt.mapping.network_view = network_view
        if network_view_exists is False:
            self.ib_cxt.mapping.network_view_id = None
            self.ib_cxt.mapping.authority_member = None
        else:
            self.ib_cxt.mapping.network_view_id = str.format("%s-id",
                                                             network_view)
            self.ib_cxt.mapping.authority_member = mock.Mock()


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
            self.ib_cxt.ibom.create_network_view.assert_called_once_with(
                network_view, None)

        self.ib_cxt.ibom.network_exists.assert_called_once_with(
            network_view, subnet['cidr'])

        self.ib_cxt.ibom.create_network.assert_called_once_with(
            network_view, subnet['cidr'], nameservers=[],
            dhcp_members=[], gateway_ip=subnet['gateway_ip'],
            relay_trel_ip=None, extattrs=None)

        self.ib_cxt.ibom.create_ip_range.assert_called_once_with(
            network_view,
            subnet['allocation_pools'][0]['start'],
            subnet['allocation_pools'][0]['end'],
            subnet['cidr'], True, None)

    def test_create_subnet_new_network_view(self):
        test_opts = dict()
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.create_subnet()

        self.validate_network_creation(self.helper.options['network_view'],
                                       self.helper.subnet)

    def test_create_subnet_existing_network_view(self):
        test_opts = {'cidr': '12.12.12.0/24', 'network_view_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.create_subnet()

        self.validate_network_creation(self.helper.options['network_view'],
                                       self.helper.subnet)

    def test_create_subnet_existing_private_network(self):
        test_opts = {'network_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        self.assertRaises(exc.InfobloxPrivateSubnetAlreadyExist,
                          ipam_controller.create_subnet)

    def test_create_subnet_existing_external_network(self):
        test_opts = {'network_name': 'extnet',
                     'subnet_name': 'extsub',
                     'cidr': '172.192.1.0/24',
                     'external': True,
                     'network_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.create_subnet()

        self.ib_cxt.ibom.get_network.assert_called_once_with(
            self.helper.options['network_view'], self.helper.subnet['cidr'])
        self.ib_cxt.ibom.update_network_options.assert_called_once_with(
            mock.ANY, None)

    def test_delete_subnet_for_private_network(self):
        test_opts = {'network_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.delete_subnet()

        self.ib_cxt.ibom.delete_network.assert_called_once_with(
            self.helper.options['network_view'], self.helper.subnet['cidr'])

    def test_delete_subnet_for_external_network_not_deletable(self):
        test_opts = {'external': True, 'network_exists': True}
        self.helper.prepare_test(test_opts)

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.delete_subnet()

        self.ib_cxt.ibom.delete_network.assert_not_called()

    def test_delete_subnet_for_external_network_deletable(self):
        test_opts = {'external': True, 'network_exists': True}
        self.helper.prepare_test(test_opts)
        self.grid_config.admin_network_deletion = True

        ipam_controller = ipam.IpamSyncController(self.ib_cxt)
        ipam_controller.delete_subnet()

        self.ib_cxt.ibom.delete_network.assert_called_once_with(
            self.helper.options['network_view'], self.helper.subnet['cidr'])


class IpamAsyncControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(IpamAsyncControllerTestCase, self).setUp()
        self.helper = IpamControllerTestHelper()
        self.ib_cxt = self.helper.ib_cxt

    def test_create_network_sync(self):
        pass
