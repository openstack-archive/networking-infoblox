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

from oslo_log import log as logging
from oslo_service import loopingcall
#from oslo_service import service

from neutron.agent.common import config as agent_conf
from neutron.agent import rpc as agent_rpc
from neutron.common import config as common_conf
from neutron.common import topics
from neutron import context
from neutron import manager
from neutron.i18n import _LE, _LI, _LW
from neutron.ipam.drivers.infoblox.agent import notification
from neutron.ipam.drivers.infoblox.common import config as ib_conf
from neutron import service as n_service


LOG = logging.getLogger(__name__)


class IpamAgent(manager.Manager):
    # FIXME: This might not need since plugin_rpc is not set
    # we will keep as it is for now in case we need to extend IpamAgent
    # functionality
    AGENT_TOPIC = 'infoblox_ipam_agent'

    def __init__(self, host=None):
        super(IpamAgent, self).__init__(host)

        self.conf = ib_conf.CONF
        self.conf_ipam = ib_conf.CONF_IPAM
        self.context = context.get_admin_context_without_session()
        self.report_interval = self.conf.AGENT.report_interval

        self._setup_rpc()

    def _setup_rpc(self):
        #self.plugin_rpc
        self.notification_service = notification.NotificationService()
        self.notification_service.start()
        self.notification_service.wait()


class IpamAgentWithStateReport(IpamAgent):
    def __init__(self, host=None):
        super(IpamAgentWithStateReport, self).__init__(host)

        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)

        self.agent_state = {
            'binary': 'infoblox-ipam-agent',
            'host': host,
            'topic': self.AGENT_TOPIC,
            'configurations': {},
            'start_flag': True,
            'agent_type': 'Infoblox IPAM agent'}

        self.use_call = True

        if self.report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=self.report_interval)

    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context, self.agent_state,
                                        self.use_call)
            self.agent_state.pop('start_flag', None)
            self.use_call = False
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_LW("The agent does not support state report."
                         " State report for this agent will be disabled."))
            self.heartbeat.stop()
            return
        except Exception:
            LOG.exception(_LE("Failed reporting state!"))
            return

    def agent_updated(self, context, payload):
        LOG.info(_LI("agent_updated by server side %s!"), payload)


def main():
    agent_conf.register_agent_state_opts_helper(ib_conf.CONF)
    common_conf.init(sys.argv[1:])
    common_conf.setup_logging()

    try:
        server = n_service.Service.create(
            binary='infoblox-ipam-agent',
            topic=IpamAgent.AGENT_TOPIC,
            report_interval=ib_conf.CONF.AGENT.report_interval,
            manager='neutron.ipam.drivers.infoblox.agent.'
                    'ipam_agent.IpamAgentWithStateReport')
        n_service.launch(server).wait()
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        sys.exit(_("ERROR: %s") % e)
