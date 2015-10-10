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

from oslo_config import cfg

from neutron.common import config as common_config
from neutron import context

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import notification
from networking_infoblox.neutron.common import utils
from networking_infoblox.tests import base


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
        self._setup_grid_config()

    def _setup_grid_config(self):
        # config init is needed to initialize transport and config loading
        common_config.init([])

        # register infoblox stanza
        config.register_infoblox_ipam_opts(cfg.CONF)
        cfg.CONF.set_override("cloud_data_center_id", '1000', 'infoblox')
        cfg.CONF.set_override("ipam_agent_workers", '1', 'infoblox')

        # register infoblox data center stanza
        data_center_id = cfg.CONF.infoblox.cloud_data_center_id
        config.register_infoblox_grid_opts(cfg.CONF, data_center_id)
        data_center = 'infoblox-dc:%s' % data_center_id
        cfg.CONF.set_override('grid_master_host', '192.168.1.21', data_center)
        cfg.CONF.set_override('data_center_name', 'admin', data_center)
        cfg.CONF.set_override('admin_user_name', 'admin', data_center)
        cfg.CONF.set_override('admin_password', 'infoblox', data_center)
        cfg.CONF.set_override('cloud_user_name', 'cloud', data_center)
        cfg.CONF.set_override('cloud_user_password', 'cloud', data_center)
        cfg.CONF.set_override('wapi_version', '2.2', data_center)

        # plugin
        cfg.CONF.set_override('core_plugin',
                              'neutron.plugins.ml2.plugin.Ml2Plugin')

    def test_notification_endpoint_with_notification_handler(self):
        msg_context = {}
        publisher_id = 'test_publisher'
        payload = {}
        metadata = {}

        endpoint = notification.NotificationEndpoint(self.ctx)

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
            self.assertEqual(endpoint.received_payload[i], test_msg_payload[i])
