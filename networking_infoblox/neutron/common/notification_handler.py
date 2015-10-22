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

from networking_infoblox.neutron.common import context
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class IpamEventHandler(object):

    traceable = True

    def __init__(self, neutron_context, plugin=None, grid_manager=None):
        self.context = neutron_context
        self.plugin = plugin if plugin else manager.NeutronManager.get_plugin()
        self.grid_mgr = (grid_manager if grid_manager else
                         grid.GridManager(self.context))
        self.grid_mgr.sync()

        self.grid_config = self.grid_mgr.grid_config
        self.grid_id = self.grid_config.grid_id

        self._cached_grid_members = None
        self._cached_network_views = None
        self._cached_mapping_conditions = None

    def _resync(self):
        self.grid_mgr.sync()

        self._cached_grid_members = dbi.get_members(
            self.context.session, grid_id=self.grid_id)
        self._cached_network_views = dbi.get_network_views(
            self.context.session, grid_id=self.grid_id)
        self._cached_mapping_conditions = dbi.get_mapping_conditions(
            self.context.session, grid_id=self.grid_id)

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
        """Notifies that new networks are about to be created.

        Upon alert, trigger grid sync and record tenant names
        """
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        if self.traceable:
            for network in networks:
                LOG.debug("network: %s" % network)

        self._resync()

    def create_subnet_alert(self, payload):
        """Notifies that new subnets are about to be created.

        Upon alert, trigger grid sync and record tenant names
        """
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        if self.traceable:
            for subnet in subnets:
                LOG.debug("subnet: %s" % subnet)

        self._resync()

    def create_network_sync(self, payload):
        """Notifies that new networks have been created."""
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        for network in networks:
            if self.traceable:
                LOG.debug("network: %s" % network)

            ib_context = context.InfobloxContext(self.context, self.user_id,
                                                 network, None,
                                                 self.grid_config, self.plugin)
            ipam_controller = ipam.IpamAsyncController(ib_context)
            ipam_controller.create_network_sync()

    def update_network_sync(self, payload):
        """Notifies that the network property has been updated."""
        network = payload.get('network')

        if self.traceable:
            LOG.debug("network: %s" % network)

        ib_context = context.InfobloxContext(self.context, self.user_id,
                                             network, None, self.grid_config,
                                             self.plugin)
        ipam_controller = ipam.IpamAsyncController(ib_context)
        ipam_controller.update_network_sync()

    def delete_network_sync(self, payload):
        """Notifies that the network has been deleted."""
        network_id = payload.get('network_id')

        if self.traceable:
            LOG.debug("network_id: %s" % network_id)

        # At this point, NIOS subnets that belong to the networks
        # should have been removed; check if still exists and remove them
        # if necessary.
        ib_context = context.InfobloxContext(self.context, self.user_id,
                                             None, None, self.grid_config,
                                             self.plugin)
        ipam_controller = ipam.IpamAsyncController(ib_context)
        ipam_controller.update_network_sync()

        self._resync()

    def create_subnet_sync(self, payload):
        """Notifies that new subnets have been created.

        We have two ways to get physical network info.
        1. Create/update network sync can get this info and cache it in DB.
        2. Call plugin.get_network() directly

        If we choose 2, then we can actually do this in ipam driver but not
        sure if this is acceptable by community. We can do this in the
        notification handler.
        """
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        # get network from plugin so that physical network info is available.
        network_id = subnets[0].get('network_id')
        network = self.plugin.get_network(self.context, network_id)

        for subnet in subnets:
            if self.traceable:
                LOG.debug("subnet: %s" % subnet)

            ib_context = context.InfobloxContext(
                self.context, self.user_id, network, subnet, self.grid_config,
                self.plugin, self._cached_grid_members,
                self._cached_network_views, self._cached_mapping_conditions)

            ipam_controller = ipam.IpamAsyncController(ib_context)
            ipam_controller.create_subnet_sync()

        self._resync()

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

        self._resync()

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
