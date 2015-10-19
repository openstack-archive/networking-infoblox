# Copyright 2015 OpenStack LLC.
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


LOG = logging.getLogger(__name__)


class DhcpSyncDriver(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id

    def create_subnet(self):
        pass

    def update_subnet(self):
        pass

    def delete_subnet(self, subnet_id):
        pass

    def allocate_ip(self, ip_address, port_id, device_owner, device_id):
        pass

    def deallocate_ip(self, port):
        pass


class DhcpAsyncDriver(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id

    def create_network_sync(self):
        """Manages DHCP relay management ips."""
        pass

    def update_network_sync(self):
        """Updates EAs for each subnet that belong to the updated network."""
        pass

    def delete_network_sync(self, network_id):
        """Deletes infoblox entities that are associated with neutron network.

        db_base_plugin_v2 delete_network calls delete_subnet per subnet under
        the network so subnet deletion is not concerned here.
        """
        pass

    def create_subnet_sync(self):
        """Updates Physical network related EAs."""
        pass

    def create_floatingip_sync(self, port):
        pass

    def update_floatingip_sync(self, port_id):
        pass

    def delete_floatingip_sync(self, port_id):
        pass
