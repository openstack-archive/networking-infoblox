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
from neutron import context
from neutron.tests.unit import testlib_api

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.db import infoblox_db as dbi
from networking_infoblox.tests import base


class DnsControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(DnsControllerTestCase, self).setUp()
        self.neutron_cxt = context.get_admin_context()
        self.test_dns_zone = 'infoblox.com'
        self.ib_cxt = self._get_ib_context()
        self.ib_cxt.context = self.neutron_cxt
        self.test_zone_format = "IPV%s" % self.ib_cxt.subnet['ip_version']
        self.controller = dns.DnsController(self.ib_cxt)
        self.controller.pattern_builder = mock.Mock()
        self.controller.pattern_builder.get_zone_name.return_value = (
            self.test_dns_zone)

    def _get_ib_context(self):
        ib_cxt = mock.Mock()
        ib_cxt.network = {'id': 'network-id',
                          'name': 'test-net-1',
                          'tenant_id': 'network-id'}
        ib_cxt.subnet = {'id': 'subnet-id',
                         'name': 'test-sub-1',
                         'tenant_id': 'tenant-id',
                         'network_id': 'network-id',
                         'cidr': '11.11.1.0/24',
                         'ip_version': 4}
        ib_cxt.tenant_id = ib_cxt.network['tenant_id']
        ib_cxt.mapping.dns_view = 'test-dns-view'
        ib_cxt.get_dns_members.return_value = ([mock.ANY], None)
        ib_cxt.grid_config.ns_group = None
        ib_cxt.grid_config.default_domain_name_pattern = self.test_dns_zone
        return ib_cxt

    def test_create_dns_zones_without_ns_group(self):
        rollback_list = []
        self.controller.create_dns_zones(rollback_list)

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                grid_primary=[mock.ANY],
                grid_secondaries=None,
                extattrs=mock.ANY),
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                grid_primary=[mock.ANY],
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=mock.ANY)
        ]

    def test_create_dns_zones_with_ns_group(self):
        rollback_list = []
        self.ib_cxt.grid_config.ns_group = 'test-ns-group'
        self.controller.create_dns_zones(rollback_list)

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                ns_group=self.ib_cxt.grid_config.ns_group,
                extattrs=mock.ANY),
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=mock.ANY)
        ]

    def _create_ib_zone_ea(self):
        zone_ea = {'CMP Type': {'value': 'OpenStack'},
                   'Cloud API Owned': {'value': 'True'},
                   'Tenant ID': {'value': 'test-id'},
                   'Tenant Name': {'value': 'tenant-name'},
                   'Account': {'value': 'admin'},
                   'Network View ID': {'value': 'default'}}
        return ib_objects.EA.from_dict(zone_ea)

    def _reset_ib_zone_ea(self):
        expected_ea = {'Cloud API Owned': {'value': 'False'},
                       'CMP Type': {'value': 'N/A'},
                       'Tenant ID': {'value': 'N/A'}}
        return expected_ea

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    def test_delete_dns_zones_for_shared_network_view(self):
        self.ib_cxt.mapping.shared = True
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        ib_zone_ea = self._create_ib_zone_ea()
        ib_zone_mock = mock.Mock(extattrs=ib_zone_ea)

        with mock.patch.object(ib_objects.DNSZone,
                               'search',
                               return_value=ib_zone_mock):
            self.controller.delete_dns_zones()
            assert ib_zone_mock.extattrs.to_dict() == ib_zone_ea.to_dict()

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    def test_delete_dns_zones_for_external_network(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = True
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        ib_zone_ea = self._create_ib_zone_ea()
        ib_zone_mock = mock.Mock(extattrs=ib_zone_ea)

        with mock.patch.object(ib_objects.DNSZone,
                               'search',
                               return_value=ib_zone_mock):
            self.controller.delete_dns_zones()
            assert ib_zone_mock.extattrs.to_dict() == ib_zone_ea.to_dict()

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_shared_network(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = True
        self.ib_cxt.grid_config.admin_network_deletion = False

        ib_zone_ea = self._create_ib_zone_ea()
        ib_zone_mock = mock.Mock(extattrs=ib_zone_ea)

        with mock.patch.object(ib_objects.DNSZone,
                               'search',
                               return_value=ib_zone_mock):
            self.controller.delete_dns_zones()
            assert ib_zone_mock.extattrs.to_dict() == ib_zone_ea.to_dict()

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_shared_network_with_admin_network_deletable(
            self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = True
        self.ib_cxt.grid_config.admin_network_deletion = True

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_static_zone(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = True

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_subnet_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{subnet_name}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert not dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_network', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_network_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{network_id}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_network.called

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_tenant', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_tenant_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{tenant_name}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_tenant.called

    @mock.patch.object(dbi, 'get_network_views', mock.Mock())
    @mock.patch.object(dbi, 'is_last_subnet_in_address_scope', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_address_scope_pattern(
            self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{address_scope_id}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network_is_shared = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_address_scope.called

    def test_bind_names(self):
        ip_address = '11.11.1.2'
        instance_name = 'test-vm'
        tenant_id = 'tenant-id'
        port_id = 'port-id'
        device_id = 'device-id'
        self.ib_cxt.user_id = 'test-id'
        self.ib_cxt.mapping.network_view = 'test-view'

        fqdn = str.format("{}.{}", instance_name, self.test_dns_zone)
        self.controller.pattern_builder.get_hostname.return_value = fqdn

        self.controller.bind_names(ip_address, instance_name, port_id,
                                   port_tenant_id=tenant_id,
                                   device_id=device_id,
                                   device_owner=None)
        assert self.ib_cxt.ip_alloc.method_calls == []

        device_owner = n_const.DEVICE_OWNER_DHCP
        self.controller.bind_names(ip_address, instance_name, port_id,
                                   port_tenant_id=tenant_id,
                                   device_id=device_id,
                                   device_owner=device_owner)
        assert self.ib_cxt.dhcp_port_ip_alloc.method_calls[0] == (
            mock.call.bind_names(self.ib_cxt.mapping.network_view,
                                 self.ib_cxt.mapping.dns_view,
                                 ip_address,
                                 fqdn,
                                 mock.ANY)
        )

        device_owner = n_const.DEVICE_OWNER_ROUTER_GW
        self.controller.bind_names(ip_address, instance_name, port_id,
                                   port_tenant_id=tenant_id,
                                   device_id=device_id,
                                   device_owner=device_owner)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.bind_names(self.ib_cxt.mapping.network_view,
                                 self.ib_cxt.mapping.dns_view,
                                 ip_address,
                                 fqdn,
                                 mock.ANY)
        ]

    def test_unbind_names(self):
        ip_address = '11.11.1.2'
        instance_name = 'test-vm'
        port_id = 'port-id'

        fqdn = str.format("{}.{}", instance_name, self.test_dns_zone)
        self.controller.pattern_builder.get_hostname.return_value = fqdn

        self.controller.unbind_names(ip_address, instance_name, port_id,
                                     device_owner=None)
        assert self.ib_cxt.ip_alloc.method_calls == []

        self.controller.unbind_names(ip_address, instance_name, port_id,
                                     device_owner=n_const.DEVICE_OWNER_DHCP)
        assert self.ib_cxt.dhcp_port_ip_alloc.method_calls == [
            mock.call.unbind_names(self.ib_cxt.mapping.network_view,
                                   self.ib_cxt.mapping.dns_view,
                                   ip_address,
                                   fqdn,
                                   mock.ANY)
        ]

        self.controller.unbind_names(
            ip_address, instance_name, port_id,
            device_owner=n_const.DEVICE_OWNER_ROUTER_GW)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.unbind_names(self.ib_cxt.mapping.network_view,
                                   self.ib_cxt.mapping.dns_view,
                                   ip_address,
                                   fqdn,
                                   mock.ANY)
        ]
