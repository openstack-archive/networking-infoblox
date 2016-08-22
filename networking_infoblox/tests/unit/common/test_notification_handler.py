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

from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants
from networking_infoblox.neutron.common import context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import notification_handler as handler
from networking_infoblox.neutron.db import infoblox_db as dbi
from networking_infoblox.tests import base


class TestIpamEventHandler(base.TestCase):

    def setUp(self):
        super(TestIpamEventHandler, self).setUp()
        self.prepare_ipam_event_handler()

    def prepare_ipam_event_handler(self):
        self.context = mock.Mock()
        self.plugin = mock.Mock()
        self.grid_manager = mock.Mock()
        self.grid_manager.grid_config.gm_connector = mock.Mock()
        self.grid_manager.grid_config.gm_connector.wapi_version = '2.0'
        self.grid_manager.grid_config.zone_creation_strategy = (
            constants.GRID_CONFIG_DEFAULTS[
                constants.EA_GRID_CONFIG_ZONE_CREATION_STRATEGY])

        self.ipam_handler = handler.IpamEventHandler(self.context, self.plugin,
                                                     self.grid_manager)
        self.ipam_handler.user_id = 'test-user'
        self.ipam_handler._resync = mock.Mock()

    def test_create_network_alert_should_call_resync(self):
        payload = {'network': {}}
        self.ipam_handler.create_network_alert(payload)
        self.ipam_handler._resync.assert_called_once_with()

    def test_create_subnet_alert_should_call_resync(self):
        payload = {'subnet': {}}
        self.ipam_handler.create_subnet_alert(payload)
        self.ipam_handler._resync.assert_called_once_with()

    def test_update_network_sync(self):
        payload = {'network': {}}
        with mock.patch.object(ipam.IpamAsyncController,
                               'update_network_sync') as controller_mock:
            self.ipam_handler.update_network_sync(payload)
        controller_mock.assert_called_once_with(False)

    @mock.patch.object(dbi, 'get_network', mock.Mock())
    @mock.patch.object(dbi, 'add_or_update_network', mock.Mock())
    def test_update_network_sync_name_not_changed(self):
        net_id = 'net_id'
        net_name = 'new_name'
        payload = {'network': {'name': net_name, 'id': net_id}}
        old_network = mock.Mock()
        old_network.network_name = net_name
        dbi.get_network.return_value = old_network
        with mock.patch.object(ipam.IpamAsyncController,
                               'update_network_sync') as controller_mock:
            self.ipam_handler.update_network_sync(payload)
        controller_mock.assert_called_once_with(False)
        dbi.get_network.assert_called_once_with(mock.ANY, net_id)
        dbi.add_or_update_network.assert_not_called()

    @mock.patch.object(dbi, 'get_network')
    @mock.patch.object(dbi, 'add_or_update_network')
    def _test_update_network_name(self, pattern, need_zones,
                                  add_or_update_network_mock,
                                  get_network_mock):
        net_id = 'net_id'
        net_name = 'new_name'
        payload = {'network': {'name': net_name, 'id': net_id}}
        old_network = mock.Mock()
        old_network.network_name = 'old_name'
        get_network_mock.return_value = old_network
        grid_config = self.grid_manager.grid_config
        grid_config.default_domain_name_pattern = pattern
        with mock.patch.object(ipam.IpamAsyncController,
                               'update_network_sync') as controller_mock:
            self.ipam_handler.update_network_sync(payload)
        controller_mock.assert_called_once_with(need_zones)
        get_network_mock.assert_called_once_with(mock.ANY, net_id)
        add_or_update_network_mock.assert_called_once_with(
            mock.ANY, net_id, net_name)

    def test_network_name_changed_zones_needed(self):
        self._test_update_network_name('{network_name}', True)

    def test_network_name_changed_zones_not_needed(self):
        self._test_update_network_name('{subnet_name}', False)

    def test_create_subnet_sync_should_call_resync(self):
        payload = {'subnet': {}}
        self.ipam_handler.create_subnet_sync(payload)
        self.ipam_handler._resync.assert_called_once_with(True)

    def test_delete_subnet_sync(self):
        payload = {'subnet_id': 'subnet-id'}
        self.ipam_handler.delete_subnet_sync(payload)
        self.ipam_handler._resync.assert_called_once_with(True)

    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_update_floatingip_sync(self, ib_cxt_mock):
        payload = {'floatingip': {'id': 'floatingip-id',
                                  'tenant_id': 'tenant-id',
                                  'port_id': 'port-id',
                                  'floating_network_id': 'floating-network-id',
                                  'floating_ip_address': '8.8.8.3'}}
        instance_name = 'test-inst'
        self.ipam_handler._get_instance_name_from_fip = (
            mock.Mock(return_value=instance_name))
        ib_cxt_mock.grid_config.default_domain_name_pattern = 'global.com'
        self.ipam_handler._get_mapping_neutron_subnet = mock.Mock()
        with mock.patch.object(dns.DnsController,
                               'bind_names') as bind_name_mock:
            self.ipam_handler.update_floatingip_sync(payload)
        bind_name_mock.assert_called_with(
            payload['floatingip']['floating_ip_address'],
            instance_name,
            mock.ANY,
            payload['floatingip']['tenant_id'],
            mock.ANY,
            mock.ANY,
            True,
            mock.ANY)

    @mock.patch.object(dbi, 'get_instance', mock.Mock())
    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_get_instance_name_from_fip(self, ib_cxt_mock):
        floatingip = {'id': 'floatingip-id',
                      'tenant_id': 'tenant-id',
                      'port_id': 'port-id',
                      'floating_network_id': 'floating-network-id',
                      'floating_ip_address': '8.8.8.3',
                      'fixed_ip_address': '1.1.1.1'}
        port = {'fixed_ips': [{'subnet_id': 'subnet-id',
                               'ip_address': floatingip['fixed_ip_address']}],
                'device_id': 'instance-id1',
                'device_owner': 'compute:nova'}
        instance_name = 'test-inst'
        extattrs = mock.Mock(extattrs={'VM Name': instance_name})
        dbi.get_instance.return_value = None
        self.plugin.get_port = mock.Mock(return_value=port)
        self.plugin.get_subnet = mock.Mock()
        with mock.patch.object(ib_objects.FixedAddress,
                               'search',
                               return_value=extattrs):
            self.assertEqual(
                instance_name,
                self.ipam_handler._get_instance_name_from_fip(floatingip))
            self.plugin.get_port.assert_called_with(mock.ANY,
                                                    floatingip['port_id'])
            self.plugin.get_subnet.assert_called_with(
                mock.ANY, port['fixed_ips'][0]['subnet_id'])
            # now check with instance in db
            dbi.get_instance.return_value = mock.Mock()
            dbi.get_instance.return_value.instance_name = instance_name
            self.plugin.get_port.reset_mock()
            self.plugin.get_subnet.reset_mock()
            self.assertEqual(
                instance_name,
                self.ipam_handler._get_instance_name_from_fip(floatingip))
            self.plugin.get_port.assert_called_with(mock.ANY,
                                                    floatingip['port_id'])
            self.plugin.get_subnet.assert_not_called()

    def _prepare_context(self):
        message_context = {'project_name': u'admin',
                           'user_id': u'9510723b6555473cb735ce6640e680cb',
                           'show_deleted': False,
                           'roles': [u'admin'],
                           'tenant_name': u'admin',
                           'auth_token': u'dd7257d2e02f41c2908ffdc197af9061',
                           'tenant_id': u'bf0806763e32436bbdb8fd9b6ebfac93',
                           'tenant': u'bf0806763e32436bbdb8fd9b6ebfac93',
                           'user_name': u'admin'}
        self.ipam_handler.ctxt = message_context

    def test_create_network_sync_same_tenant(self):
        payload = {
            'network': {'status': 'ACTIVE',
                        'subnets': [],
                        'name': 'network_name',
                        'tenant_id': 'bf0806763e32436bbdb8fd9b6ebfac93'}}
        self._prepare_context()
        self.ipam_handler.create_network_sync(payload)

    @mock.patch('networking_infoblox.neutron.db.infoblox_db.get_tenants')
    def test_create_network_sync_tenant_mismatch(self, get_mock):
        db_tenant = mock.Mock()
        db_tenant.id = '25ba7c0a7b1e4266b48a7731b2502e05'
        get_mock.return_value = [mock.Mock()]
        payload = {
            'network': {'status': 'ACTIVE',
                        'subnets': [],
                        'name': 'network_name',
                        'tenant_id': db_tenant.id}}
        self._prepare_context()
        self.ipam_handler.create_network_sync(payload)

    @mock.patch.object(dbi, 'add_or_update_instance', mock.Mock())
    def test_create_instance_sync_instance_name_create(self):
        instance_id = 'instance-id'
        instance_name = 'test-host'
        payload = {
            'instance_id': instance_id,
            'hostname': instance_name,
            'fixed_ips': {}
            }
        self._prepare_context()
        self.ipam_handler.create_instance_sync(payload)
        dbi.add_or_update_instance.assert_called_once_with(
            self.context.session, instance_id, instance_name)

    @mock.patch.object(dbi, 'remove_instance', mock.Mock())
    @mock.patch.object(dbi, 'get_external_subnets', mock.Mock())
    def test_delete_instance_sync_instance_name_delete(self):
        instance_id = 'instance-id'
        payload = {
            'instance_id': instance_id,
            }
        self._prepare_context()
        dbi.get_external_subnets.return_value = ()
        self.ipam_handler.delete_instance_sync(payload)
        dbi.remove_instance.assert_called_once_with(
            self.context.session, instance_id)

    @mock.patch.object(dbi, 'add_or_update_instance', mock.Mock())
    @mock.patch.object(context, 'InfobloxContext', mock.Mock())
    @mock.patch.object(dns, 'DnsController', mock.Mock())
    def test_create_instance_bind_names(self):
        instance_id = 'instance-id'
        instance_name = 'test-host'
        dns_controller = mock.MagicMock()
        dns.DnsController.return_value = dns_controller
        payload = {
            'instance_id': instance_id,
            'hostname': instance_name,
            'fixed_ips': [
                {'address': 'adr-1', 'subnet_id': 'subnet-1'},
                {'address': 'adr-2', 'subnet_id': 'subnet-2'},
                {'address': 'adr-3', 'subnet_id': 'subnet-3'},
                {'address': 'adr-4', 'subnet_id': 'subnet-4'},
            ]
        }
        self._prepare_context()
        ports = [
            {
                'id': 'port-id-1',
                'name': 'port-name-1',
                'tenant_id': 'tenant-id-1',
                'device_id': 'device-id-1',
                'device_owner': 'device-owner-1',
                'fixed_ips': [
                    {'ip_address': 'adr-1', 'subnet_id': 'subnet-1'},
                    {'ip_address': 'adr-2', 'subnet_id': 'subnet-2'},
                ]
            },
            {
                'id': 'port-id-2',
                'name': 'port-name-2',
                'tenant_id': 'tenant-id-2',
                'device_id': 'device-id-2',
                'device_owner': 'device-owner-2',
                'fixed_ips': [
                    {'ip_address': 'adr-3', 'subnet_id': 'subnet-3'},
                    {'ip_address': 'adr-4', 'subnet_id': 'subnet-4'},
                ]
            },
        ]
        with mock.patch.object(self.ipam_handler, 'plugin'):
            self.ipam_handler.plugin.get_ports.return_value = ports
            self.ipam_handler.create_instance_sync(payload)
            assert dns_controller.method_calls == [
                mock.call.bind_names(
                    'adr-1', 'test-host', 'port-id-1', 'tenant-id-1',
                    'device-id-1', 'device-owner-1', port_name='port-name-1'),
                mock.call.bind_names(
                    'adr-2', 'test-host', 'port-id-1', 'tenant-id-1',
                    'device-id-1', 'device-owner-1', port_name='port-name-1'),
                mock.call.bind_names(
                    'adr-3', 'test-host', 'port-id-2', 'tenant-id-2',
                    'device-id-2', 'device-owner-2', port_name='port-name-2'),
                mock.call.bind_names(
                    'adr-4', 'test-host', 'port-id-2', 'tenant-id-2',
                    'device-id-2', 'device-owner-2', port_name='port-name-2')
            ]

    @mock.patch.object(dbi, 'get_instance', mock.Mock())
    @mock.patch.object(context, 'InfobloxContext', mock.Mock())
    @mock.patch.object(dns, 'DnsController', mock.Mock())
    def test_update_port_sync(self):
        subnet_id = 'test-subnet'
        port_name = 'test-port'
        port_id = 'test-port-id'
        ip_address = '192.168.126.4'
        instance_id = 'test-instance-id'
        instance_name = 'test-instance'
        network_id = 'test-network-id'
        tenant_id = 'test-tenant-id'
        nova = constants.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA
        payload_attach = {
            'port': {
                'device_owner': nova,
                'fixed_ips': [{'subnet_id': subnet_id,
                               'ip_address': ip_address}],
                'id': port_id,
                'binding:vif_type': 'ovs',
                'device_id': instance_id,
                'name': port_name,
                'network_id': network_id,
                'tenant_id': tenant_id,
            }
        }
        payload_detach = {
            'port': {
                'device_owner': '',
                'fixed_ips': [{'subnet_id': subnet_id,
                               'ip_address': ip_address}],
                'id': port_id,
                'binding:vif_type': 'unbound',
                'device_id': '',
                'name': port_name,
                'network_id': network_id,
                'tenant_id': tenant_id,
            }
        }
        dns_controller = mock.MagicMock()
        dns.DnsController.return_value = dns_controller
        instance = mock.MagicMock()
        instance.instance_name = instance_name
        dbi.get_instance.return_value = instance
        # Attach port and ensure that bind_names called
        self.ipam_handler.update_port_sync(payload_attach)
        dns_controller.method_calls == [
            mock.call.bind_names(
                ip_address, instance_name, port_id, tenant_id, instance_id,
                nova, port_name=port_name)]
        # now detach port and ensure that unbind_names called
        self.ipam_handler.update_port_sync(payload_detach)
        dns_controller.method_calls == [
            mock.call.bind_names(
                ip_address, instance_name, port_id, tenant_id, instance_id,
                nova, port_name=port_name),
            mock.call.unbind_names(
                ip_address, None, port_id, tenant_id, None, 'compute:nova',
                port_name=port_name)
        ]
