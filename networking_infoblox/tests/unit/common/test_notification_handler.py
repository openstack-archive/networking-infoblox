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

    def test_delete_network_sync(self):
        payload = {'network': {}, 'network_id': 'network-id'}
        with mock.patch.object(ipam.IpamAsyncController,
                               'delete_network_sync') as controller_mock:
            self.ipam_handler.delete_network_sync(payload)
        controller_mock.assert_called_once_with(payload['network_id'])
