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

import eventlet
eventlet.monkey_patch()

import mock
import time

from neutron import context

from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import notification
from networking_infoblox.neutron.common import notification_handler
from networking_infoblox.neutron.common import utils

from networking_infoblox.tests import base
from networking_infoblox.tests.unit import grid_sync_stub


class NotificationTestCase(base.RpcTestCase):

    class NotificationEndpointTester(object):
        received_msg_count = 0
        received_payload = []

        def info(self, ctxt, publisher_id, event_type, payload, metadata):
            self.received_payload.append(payload)
            self.received_msg_count += 1

    def setUp(self):
        super(NotificationTestCase, self).setUp()
        self.ctx = context.get_admin_context()
        stub = grid_sync_stub.GridSyncStub(self.ctx, self.connector_fixture)
        stub.prepare_grid_manager(wapi_version='2.2')
        self.grid_mgr = stub.get_grid_manager()
        self.grid_mgr.grid_config.grid_sync_support = False
        self.grid_mgr.last_sync_time = mock.Mock()
        self.grid_mgr.grid_config.gm_connector = mock.Mock()
        self.grid_mgr.grid_config.gm_connector.wapi_version = '2.0'
        self.event_handler = notification_handler.IpamEventHandler(
            self.ctx, mock.Mock(), self.grid_mgr)

    @mock.patch.object(notification_handler, 'IpamEventHandler', mock.Mock())
    def test_notification_endpoint_with_notification_handler(self):
        msg_context = {}
        publisher_id = 'test_publisher'
        payload = {}
        metadata = {}

        endpoint = notification.NotificationEndpoint(self.ctx, None)
        endpoint.handler = self.event_handler

        # go through each event type and verify that each event handler is
        # called from notification handler
        event_types = notification.NotificationEndpoint.event_subscription_list
        for event_type in event_types:
            handler_name = utils.get_notification_handler_name(event_type)
            with mock.patch.object(endpoint.handler,
                                   handler_name) as handler_mock:
                endpoint.info(msg_context, publisher_id, event_type, payload,
                              metadata)
                handler_mock.assert_called_once_with(payload)

    def wait_for_messages(self, endpoint, expected_msg_count):
        while endpoint.received_msg_count < expected_msg_count:
            time.sleep(0.01)

    @mock.patch.object(notification, 'NotificationEndpoint', mock.Mock())
    @mock.patch.object(grid, 'GridManager', mock.Mock())
    def test_notification_service(self):
        publisher_id = 'test_publisher'
        topic = 'notifications'
        notifier = self.get_notifier(topic=topic, publisher_id=publisher_id)

        # prepare service
        service = notification.NotificationService(report_interval=30)
        endpoint = self.NotificationEndpointTester()
        service.event_endpoints = [endpoint]
        service.transport = self.transport
        service.start()

        # send notification messages
        test_msg_count = 5
        event_type = 'subnet.create.start'
        test_msg_payload = []
        for i in range(test_msg_count):
            test_msg = 'test message %d' % i
            notifier.info({}, event_type, test_msg)
            test_msg_payload.append(test_msg)

        self.wait_for_messages(endpoint, test_msg_count)

        service.stop()

        for i in range(test_msg_count):
            self.assertEqual(test_msg_payload[i], endpoint.received_payload[i])
