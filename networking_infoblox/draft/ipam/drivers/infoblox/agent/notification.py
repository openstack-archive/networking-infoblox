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

from oslo_log import log as logging
import oslo_messaging
from oslo_service import service

from neutron.ipam.drivers.infoblox.agent import event as ipam_event
from neutron.ipam.drivers.infoblox.common import ipam
from neutron.ipam.drivers.infoblox.common import rpc as x_rpc


LOG = logging.getLogger(__name__)


class NotificationService(service.Service):
    """Listener for notification service."""

    NOTIFICATION_TOPIC = 'notifications'

    def start(self):
        self.event_targets = [
            oslo_messaging.Target(topic=self.NOTIFICATION_TOPIC)
        ]

        controller = ipam.IpamController()
        self.event_endpoints = [
            ipam_event.IpamPostEventEndpoint(controller),
            ipam_event.InstanceEventEndpoint(controller)
        ]

        self.event_listener = x_rpc.get_notification_listener(
            self.event_targets, self.event_endpoints, allow_requeue=False)
        self.event_listener.start()

    def stop(self, graceful=False):
        if self.event_listener:
            x_rpc.kill_listeners([self.event_listener])
        super(NotificationService, self).stop(graceful)
