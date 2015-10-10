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
from oslo_utils import encodeutils

from neutron import manager

from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import utils


LOG = logging.getLogger(__name__)


class IpamEventHandler(object):

    traceable = True

    def __init__(self, context, plugin=None, grid_mgr=None):
        self.context = context
        self.plugin = plugin if plugin else manager.NeutronManager.get_plugin()
        self.grid_mgr = grid_mgr if grid_mgr else grid.GridManager(context)

    def process(self, ctxt, publisher_id, event_type, payload, metadata):
        self.ctxt = ctxt
        self.user_id = self.ctxt.get('user_id')

        try:
            handler_name = utils.get_notification_handler_name(event_type)
            handler = getattr(self, handler_name)
            if handler:
                handler(payload)
            return oslo_messaging.NotificationResult.HANDLED
        except Exception as e:
            LOG.error(encodeutils.exception_to_unicode(e))

    def create_network_alert(self, payload):
        """Notifies that new networks are about to be created."""
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        for network in networks:
            if self.traceable:
                LOG.debug("network: %s" % network)

    def create_subnet_alert(self, payload):
        """Notifies that new subnets are about to be created."""
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        for subnet in subnets:
            if self.traceable:
                LOG.debug("subnet: %s" % subnet)

    def create_network_sync(self, payload):
        """Notifies that new networks have been created."""
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        for network in networks:
            if self.traceable:
                LOG.debug("network: %s" % network)

    def update_network_sync(self, payload):
        """Notifies that the network property has been updated."""
        network = payload.get('network')

        if self.traceable:
            LOG.debug("network: %s" % network)

    def delete_network_sync(self, payload):
        """Notifies that the network has been deleted."""
        network_id = payload.get('network_id')

        if self.traceable:
            LOG.debug("network_id: %s" % network_id)

        # At this point, NIOS subnets that belong to the networks
        # should have been removed; check if still exists and remove them
        # if necessary.

    def create_subnet_sync(self, payload):
        """Notifies that new subnets have been created."""
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        for subnet in subnets:
            if self.traceable:
                LOG.debug("subnet: %s" % subnet)

    def update_subnet_sync(self, payload):
        """Notifies that the subnet has been updated."""
        subnet = payload.get('subnet')

        if self.traceable:
            LOG.debug("subnet: %s" % subnet)

    def delete_subnet_sync(self, payload):
        """Notifies that the subnet has been deleted."""
        subnet_id = payload.get('subnet_id')

        if self.traceable:
            LOG.debug("subnet_id: %s" % subnet_id)

        # At this point, NIOS subnets should have been removed.
        # Check if still exists and remove them if necessary.

    def create_port_sync(self, payload):
        """Notifies that new ports have been created."""
        if 'ports' in payload:
            ports = payload.get('ports')
        else:
            ports = [payload.get('port')]

        for port in ports:
            if self.traceable:
                LOG.debug("port: %s" % port)

    def update_port_sync(self, payload):
        """Notifies that the port has been updated."""
        port = payload.get('port')

        if self.traceable:
            LOG.debug("port: %s" % port)

    def delete_port_sync(self, payload):
        """Notifies that the port has been deleted."""
        port_id = payload.get('port_id')

        if self.traceable:
            LOG.debug("port_id: %s" % port_id)

    def create_floatingip_sync(self, payload):
        """Notifies that a new floating ip has been created.

        There are two types of responses with this event:
        1. floating ip creation: this response comes with no port_id and
        fixed_ip_address.

        2. floating ip association with fixed_ip_address: this repsponse
        contains port_id and fixed_ip_address.
        """
        floatingip = payload.get('floatingip')

        if self.traceable:
            LOG.debug("floatingip: %s" % floatingip)

        port_id = floatingip.get('port_id')

        if port_id is None:
            # call floating ip creation
            pass
        else:
            # call floating ip association
            pass

    def update_floatingip_sync(self, payload):
        """Notifies that the floating ip has been updated.

        update could be either association if port_id is not empty or
        dissociation if port_id is None.
        """
        floatingip = payload.get('floatingip')

        if self.traceable:
            LOG.debug("floatingip: %s" % floatingip)

    def delete_floatingip_sync(self, payload):
        """Notifies that the floating ip has been deleted."""
        floatingip_id = payload.get('floatingip_id')

        if self.traceable:
            LOG.debug("floatingip_id: %s" % floatingip_id)

    def create_instance_sync(self, payload):
        """Notifies that an instance has been created."""
        instance_id = payload.get('instance_id')
        host = payload.get('host')

        if self.traceable:
            LOG.debug("instance_id: %s, host: %s" % (instance_id, host))
