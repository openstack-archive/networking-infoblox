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
# We need to monkey patch the socket and select module for,
# at least, oslo.messaging, otherwise everything's blocked on its
# first read() or select(), thread need to be patched too, because
# oslo.messaging use threading.local
eventlet.monkey_patch(socket=True, select=True, thread=True, time=True)
import sys

from oslo_log import log
from oslo_service import service

from neutron.common import config as n_config
from neutron.ipam.drivers.infoblox.agent import notification


LOG = log.getLogger(__name__)


def main():
    n_config.init(sys.argv[1:])
    n_config.setup_logging()
    service.launch(notification.NotificationService()).wait()


if __name__ == "__main__":
    main()
