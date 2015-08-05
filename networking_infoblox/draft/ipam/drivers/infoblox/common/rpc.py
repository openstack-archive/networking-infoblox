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

import oslo_messaging

from neutron.common import rpc as n_rpc


# This module extends neutron.common.rpc to add notification listener
# server

def get_notification_listener(targets, endpoints,
                          allow_requeue=False):
    """Return a configured oslo_messaging notification listener."""
    return oslo_messaging.get_notification_listener(
        n_rpc.TRANSPORT, targets, endpoints, executor='eventlet',
        allow_requeue=allow_requeue)


def kill_listeners(listeners):
    """Kills notification listeners"""
    # correct usage of oslo.messaging listener is to stop(),
    # which stops new messages, and wait(), which processes remaining
    # messages and closes connection
    for listener in listeners:
        listener.stop()
        listener.wait()
