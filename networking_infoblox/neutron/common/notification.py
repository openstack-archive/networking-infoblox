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
from oslo_service import loopingcall
from oslo_service import service

from neutron.agent import rpc as agent_rpc
from neutron.common import topics
from neutron import context

from networking_infoblox._i18n import _LE
from networking_infoblox._i18n import _LW
from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import notification_handler


LOG = logging.getLogger(__name__)


class NotificationEndpoint(object):

    event_subscription_list = [
        # pre-committed ipam events
        'network.create.start',
        'subnet.create.start',
        # post-committed ipam events
        'network.create.end',
        'network.update.end',
        'network.delete.end',
        'subnet.create.end',
        'subnet.update.end',
        'subnet.delete.end',
        'port.create.end',
        'port.update.end',
        'port.delete.end',
        'floatingip.create.end',
        'floatingip.update.end',
        'floatingip.delete.end',
        # nova instance event
        'compute.instance.create.end',
        'compute.instance.delete.end']

    def __init__(self, context, grid_manager):
        self.context = context
        # Using filter in oslo_messaing 4.1.1 did not work for some reason
        # so commenting filter out
        # self.filter_rule = oslo_messaging.NotificationFilter(
        #    publisher_id='^(network|compute).*',
        #    event_type='|'.join(self.event_subscription_list))
        self.handler = notification_handler.IpamEventHandler(
            self.context, grid_manager=grid_manager)

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        if event_type in self.event_subscription_list:
            self.handler.process(ctxt, publisher_id, event_type, payload,
                                 metadata)


class NotificationService(service.Service):
    """Listener for notification service."""

    NOTIFICATION_TOPIC = 'notifications'
    RESYNC_TRY_INTERVAL = 30

    def __init__(self, report_interval=None):
        super(NotificationService, self).__init__()
        self.report_thread = None
        self.event_listener = None
        if report_interval:
            self.report_interval = report_interval
        else:
            self.report_interval = config.CONF.AGENT.report_interval
        self.context = context.get_admin_context()
        # Make sure config is in sync before using grid_sync_maximum_wait_time
        self.grid_manager = grid.GridManager(self.context)
        self.grid_syncer = grid.GridSyncer()
        self.grid_syncer.sync(True)
        self._init_agent_report_thread()
        self._init_notification_listener()
        self._init_periodic_resync()

    def _init_notification_listener(self):
        self.transport = oslo_messaging.get_transport(config.CONF)
        self.event_targets = [
            oslo_messaging.Target(exchange=const.NOTIFICATION_EXCHANGE_NEUTRON,
                                  topic=self.NOTIFICATION_TOPIC),
            oslo_messaging.Target(exchange=const.NOTIFICATION_EXCHANGE_NOVA,
                                  topic=self.NOTIFICATION_TOPIC)
        ]
        self.event_endpoints = [NotificationEndpoint(self.context,
                                                     self.grid_manager)]

    def _get_resync_interval(self):
        conf = self.grid_manager.grid_config
        try:
            return int(conf.grid_sync_maximum_wait_time)
        except TypeError:
            LOG.warning(_LE("Invalid resync interval set: %s"),
                        conf.grid_sync_maximum_wait_time)
            return self.RESYNC_TRY_INTERVAL

    def _init_periodic_resync(self):
        self.resync_thread = loopingcall.FixedIntervalLoopingCall(
            self._periodic_resync)
        self.resync_thread.start(interval=self.RESYNC_TRY_INTERVAL)

    def _periodic_resync(self):
        try:
            interval = self._get_resync_interval()
            if self.grid_syncer.is_sync_needed(interval):
                LOG.info(_LE("Initiating resync."))
                self.grid_syncer.sync(True)
        except Exception as e:
            LOG.exception(_LE("Resync failed due to error: %s"), e)

    def _init_agent_report_thread(self):
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)
        self.agent_state = {
            'binary': const.AGENT_BINARY_NAME,
            'host': config.CONF.host,
            'topic': 'N/A',
            'configurations': {},
            'start_flag': True,
            'agent_type': const.AGENT_TYPE_INFOBLOX_IPAM}
        self.use_call = True
        if self.report_interval:
            self.report_thread = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.report_thread.start(interval=self.report_interval)

    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context, self.agent_state,
                                        self.use_call)
            self.agent_state.pop('start_flag', None)
            self.use_call = False
        except AttributeError:
            # This means the server does not support report_state
            LOG.warning(_LW("infoblox-ipam-agent does not support state "
                            "report. State report for this agent will be "
                            "disabled."))
            self.report_thread.stop()
            return
        except Exception:
            LOG.exception(_LE("Failed reporting state!"))
            return

    def start(self):
        super(NotificationService, self).start()
        self.event_listener = get_notification_listener(
            self.transport,
            self.event_targets,
            self.event_endpoints,
            pool=const.AGENT_NOTIFICATION_POOL
        )
        self.event_listener.start()

    def stop(self, graceful=False):
        if self.event_listener:
            self.event_listener.stop()
            self.event_listener.wait()
        if self.report_thread:
            self.report_thread.stop()
        super(NotificationService, self).stop(graceful)


def get_notification_listener(transport, targets, endpoints,
                              allow_requeue=False, pool=None):
    """Return a configured oslo_messaging notification listener."""
    return oslo_messaging.get_notification_listener(
        transport, targets, endpoints, executor='eventlet',
        allow_requeue=allow_requeue, pool=pool)
