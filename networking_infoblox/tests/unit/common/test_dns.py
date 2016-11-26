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
from neutron_lib import constants as n_const

from neutron import context
from neutron.tests.unit import testlib_api

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import ea_manager
from networking_infoblox.neutron.db import infoblox_db as dbi
from networking_infoblox.tests import base


class DnsControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(DnsControllerTestCase, self).setUp()
        self.neutron_cxt = context.get_admin_context()
        self.test_dns_zone = 'infoblox.com'
        self.ib_cxt = self._get_ib_context()
        self.ib_cxt.context = self.neutron_cxt
        self.ib_cxt.network_is_external = False
        self.ib_cxt.grid_config.zone_creation_strategy = (
            self._get_default_zone_creation_strategy())
        self.test_zone_format = "IPV%s" % self.ib_cxt.subnet['ip_version']
        self.controller = dns.DnsController(self.ib_cxt)
        self.controller.pattern_builder = mock.Mock()
        self.controller.pattern_builder.get_zone_name.return_value = (
            self.test_dns_zone)

    @staticmethod
    def _get_default_zone_creation_strategy():
        return constants.GRID_CONFIG_DEFAULTS[
            constants.EA_GRID_CONFIG_ZONE_CREATION_STRATEGY]

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
        ib_cxt.mapping.network_view = 'test-network-view'
        ib_cxt.get_dns_members.return_value = ([mock.ANY], None)
        ib_cxt.grid_config.ns_group = None
        ib_cxt.grid_config.default_domain_name_pattern = self.test_dns_zone
        ib_cxt.grid_config.allow_static_zone_deletion = False
        return ib_cxt

    def test_create_dns_zones_without_ns_group_both_zones(self):
        rollback_list = []
        # default strategy is to create both Forward and Reverse zones
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
        self.ib_cxt.ibom.reset_mock()

        # check strategy with only Forward zone
        self.ib_cxt.grid_config.zone_creation_strategy = [
            constants.ZONE_CREATION_STRATEGY_FORWARD]
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                grid_primary=[mock.ANY],
                grid_secondaries=None,
                extattrs=mock.ANY),
        ]
        self.ib_cxt.ibom.reset_mock()

        # check strategy with only Reverse zone
        self.ib_cxt.grid_config.zone_creation_strategy = [
            constants.ZONE_CREATION_STRATEGY_REVERSE]
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                grid_primary=[mock.ANY],
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=mock.ANY)
        ]
        self.ib_cxt.ibom.reset_mock()

        # check empty strategy
        self.ib_cxt.grid_config.zone_creation_strategy = []
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == []

    def test_create_dns_zones_with_ns_group(self):
        rollback_list = []
        # default strategy is to create both Forward and Reverse zones
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
        self.ib_cxt.ibom.reset_mock()

        # check strategy with only Forward zone
        self.ib_cxt.grid_config.zone_creation_strategy = [
            constants.ZONE_CREATION_STRATEGY_FORWARD]
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                ns_group=self.ib_cxt.grid_config.ns_group,
                extattrs=mock.ANY),
        ]
        self.ib_cxt.ibom.reset_mock()

        # check strategy with only Reverse zone
        self.ib_cxt.grid_config.zone_creation_strategy = [
            constants.ZONE_CREATION_STRATEGY_REVERSE]
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=mock.ANY)
        ]

        # check empty strategy
        self.ib_cxt.ibom.reset_mock()
        self.ib_cxt.grid_config.zone_creation_strategy = []
        self.controller._update_strategy_and_eas()
        self.controller.create_dns_zones(rollback_list)
        assert self.ib_cxt.ibom.method_calls == []

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
                self.ib_cxt.subnet['cidr'])
        ]
        dbi.is_last_subnet_in_private_networks.assert_not_called()

        # Now enable static zone deletion
        self.ib_cxt.ibom.reset_mock()
        dbi.is_last_subnet_in_private_networks.reset_mock()
        self.ib_cxt.grid_config.allow_static_zone_deletion = True
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
                self.ib_cxt.subnet['cidr'])
        ]
        dbi.is_last_subnet_in_private_networks.assert_not_called()

        # Now enable static zone deletion
        self.ib_cxt.ibom.reset_mock()
        dbi.is_last_subnet_in_private_networks.reset_mock()
        self.ib_cxt.grid_config.allow_static_zone_deletion = True
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
        self.ib_cxt.network_is_shared_or_external = False

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
        self.ib_cxt.network_is_shared_or_external = False

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
        self.ib_cxt.network_is_shared_or_external = False

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
        self.ib_cxt.network_is_shared_or_external = False

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

    @mock.patch.object(dbi, 'get_instance', mock.Mock())
    @mock.patch.object(ea_manager, 'get_ea_for_ip', mock.Mock())
    def test_bind_names(self):
        ip_address = '11.11.1.2'
        instance_name = 'test-vm'
        tenant_id = 'tenant-id'
        tenant_name = 'tenant-name'
        port_id = 'port-id'
        port_name = 'port-name'
        device_id = 'device-id'
        self.ib_cxt.user_id = 'test-id'
        self.ib_cxt.mapping.network_view = 'test-view'
        self.ib_cxt.get_tenant_name.return_value = tenant_name
        instance = mock.MagicMock()
        instance.instance_name = instance_name
        dbi.get_instance.return_value = instance

        fqdn = str.format("{}.{}", instance_name, self.test_dns_zone)
        self.controller.pattern_builder.get_hostname.return_value = fqdn

        ip_alloc_method_calls = [
            mock.call.bind_names(self.ib_cxt.mapping.network_view,
                                 self.ib_cxt.mapping.dns_view,
                                 ip_address,
                                 fqdn,
                                 mock.ANY)
        ]
        ea_call_params = [
            self.ib_cxt.user_id, tenant_id, tenant_name, self.ib_cxt.network,
            port_id, device_id, 'device_owner', False, instance_name]
        test_data = [
            {
                'device_owner': None,
                'instance_name': instance_name,
                'ip_alloc': self.ib_cxt.ip_alloc,
                'ip_alloc_calls': [],
                'dbi_call_params': None,
            },
            {
                'device_owner': n_const.DEVICE_OWNER_DHCP,
                'instance_name': instance_name,
                'ip_alloc': self.ib_cxt.dhcp_port_ip_alloc,
                'ip_alloc_calls': ip_alloc_method_calls,
                'dbi_call_params': None,
            },
            {
                'device_owner': n_const.DEVICE_OWNER_ROUTER_GW,
                'instance_name': instance_name,
                'ip_alloc': self.ib_cxt.ip_alloc,
                'ip_alloc_calls': ip_alloc_method_calls,
                'dbi_call_params': None,
            },
            {
                'device_owner': constants.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA,
                'instance_name': instance_name,
                'ip_alloc': self.ib_cxt.ip_alloc,
                'ip_alloc_calls': ip_alloc_method_calls,
                'dbi_call_params': None,
            },
            {
                'device_owner': constants.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA,
                'instance_name': None,
                'ip_alloc': self.ib_cxt.ip_alloc,
                'ip_alloc_calls': ip_alloc_method_calls,
                'dbi_call_params': [self.ib_cxt.context.session, device_id],
            },
        ]

        for data in test_data:
            self.controller.bind_names(
                ip_address, data['instance_name'], port_id,
                port_tenant_id=tenant_id, device_id=device_id,
                device_owner=data['device_owner'], port_name=port_name)
            ip_alloc = data['ip_alloc']
            assert ip_alloc.method_calls == data['ip_alloc_calls']
            ip_alloc.reset_mock()
            if data['device_owner'] is None:
                ea_manager.get_ea_for_ip.assert_not_called()
            else:
                ea_call_params[6] = data['device_owner']
                ea_manager.get_ea_for_ip.assert_called_once_with(
                    *ea_call_params)
                ea_manager.get_ea_for_ip.reset_mock()
            dbi_call_params = data['dbi_call_params']
            if dbi_call_params is None:
                dbi.get_instance.assert_not_called()
            else:
                dbi.get_instance.assert_called_once_with(*dbi_call_params)
                ea_manager.get_ea_for_ip.reset_mock()

    def test_unbind_names(self):
        ip_address = '11.11.1.2'
        instance_name = 'test-vm'
        port_id = 'port-id'
        port_name = 'port-name'

        fqdn = str.format("{}.{}", instance_name, self.test_dns_zone)
        self.controller.pattern_builder.get_hostname.return_value = fqdn

        self.controller.unbind_names(ip_address, instance_name, port_id,
                                     device_owner=None, port_name=port_name)
        assert self.ib_cxt.ip_alloc.method_calls == []

        self.controller.unbind_names(ip_address, instance_name, port_id,
                                     device_owner=n_const.DEVICE_OWNER_DHCP,
                                     port_name=port_name)
        assert self.ib_cxt.dhcp_port_ip_alloc.method_calls == [
            mock.call.unbind_names(self.ib_cxt.mapping.network_view,
                                   self.ib_cxt.mapping.dns_view,
                                   ip_address,
                                   fqdn,
                                   None)
        ]

        self.controller.unbind_names(
            ip_address, instance_name, port_id,
            device_owner=n_const.DEVICE_OWNER_ROUTER_GW, port_name=port_name)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.unbind_names(self.ib_cxt.mapping.network_view,
                                   self.ib_cxt.mapping.dns_view,
                                   ip_address,
                                   fqdn,
                                   None)
        ]

    def test_unbind_names_without_name(self):
        ip_address = '11.11.1.2'
        port_id = 'port-id'
        port_name = 'port-name'
        self.ib_cxt.grid_config.default_host_name_pattern = '{instance_name}'
        self.ib_cxt.grid_config.default_domain_name_pattern = '{subnet_id}.com'
        controller = dns.DnsController(self.ib_cxt)
        controller.unbind_names(ip_address, None, port_id,
                                device_owner='compute:nova',
                                port_name=port_name)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.unbind_names(
                self.ib_cxt.mapping.network_view, self.ib_cxt.mapping.dns_view,
                ip_address, None, None)]

    def _test_update_calls(self, strategy, calls):
        self.ib_cxt.grid_config.zone_creation_strategy = strategy
        self.controller._update_strategy_and_eas()
        self.controller.update_dns_zones()
        assert self.ib_cxt.ibom.method_calls == calls
        self.ib_cxt.ibom.reset_mock()

    def test_update_dns_zones_all(self):
        self._test_update_calls(
            self._get_default_zone_creation_strategy(),
            [
                mock.call.update_dns_zone_attrs(
                    self.ib_cxt.mapping.dns_view,
                    self.test_dns_zone,
                    mock.ANY),
                mock.call.update_dns_zone_attrs(
                    self.ib_cxt.mapping.dns_view,
                    self.ib_cxt.subnet['cidr'],
                    mock.ANY)
            ])

    def test_update_dns_zones_forward(self):
        self._test_update_calls(
            [constants.ZONE_CREATION_STRATEGY_FORWARD],
            [
                mock.call.update_dns_zone_attrs(
                    self.ib_cxt.mapping.dns_view,
                    self.test_dns_zone,
                    mock.ANY),
            ])

    def test_update_dns_zones_reverse(self):
        self._test_update_calls(
            [constants.ZONE_CREATION_STRATEGY_REVERSE],
            [
                mock.call.update_dns_zone_attrs(
                    self.ib_cxt.mapping.dns_view,
                    self.ib_cxt.subnet['cidr'],
                    mock.ANY)
            ])

    def test_update_dns_zones_empty(self):
        self._test_update_calls([], [])
