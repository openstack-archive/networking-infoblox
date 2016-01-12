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

from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import notification_handler as handler
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
        controller_mock.assert_called_once_with()

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
            True)

    @mock.patch('networking_infoblox.neutron.common.context.InfobloxContext')
    def test_get_instance_name_from_fip(self, ib_cxt_mock):
        floatingip = {'id': 'floatingip-id',
                      'tenant_id': 'tenant-id',
                      'port_id': 'port-id',
                      'floating_network_id': 'floating-network-id',
                      'floating_ip_address': '8.8.8.3',
                      'fixed_ip_address': '1.1.1.1'}
        port = {'fixed_ips': [{'subnet_id': 'subnet-id',
                               'ip_address': floatingip['fixed_ip_address']}]}
        instance_name = 'test-inst'
        extattrs = mock.Mock(extattrs={'VM Name': instance_name})
        self.plugin.get_port = mock.Mock(return_value=port)
        self.plugin.get_subnet = mock.Mock()
        with mock.patch.object(ib_objects.FixedAddress,
                               'search',
                               return_value=extattrs):
            self.assertEqual(
                self.ipam_handler._get_instance_name_from_fip(floatingip),
                instance_name)
            self.plugin.get_port.assert_called_with(mock.ANY,
                                                    floatingip['port_id'])
            self.plugin.get_subnet.assert_called_with(
                mock.ANY, port['fixed_ips'][0]['subnet_id'])

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
