# Copyright 2015 Infoblox Inc.
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
from oslo_utils import excutils

from neutron.i18n import _LE
from neutron.i18n import _LI

from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class IpamSyncController(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id

    def create_subnet(self):
        """Creates subnet equivalent NIOS objects.

        infoblox context contains subnet dictionary from ipam driver and
        network from db query because only subnet data is passed

        The following NIOS objects are created.
        - network view
        - network with management ip if dhcp relay is used
        - ip range
        """
        session = self.ib_cxt.context.session
        network = self.ib_cxt.network
        subnet = self.ib_cxt.subnet

        network_id = network.get('id')
        subnet_id = subnet.get('id')

        exists_network_view = (True if self.ib_cxt.mapping.network_view_id
                               else False)

        if self.ib_cxt.mapping.authority_member is None:
            # after authority member reservation, ib_cxt.mapping is updated and
            # its connector and managers are loaded for the new member.
            self.ib_cxt.reserve_authority_member()

        # create a network view if it does not exist
        if not exists_network_view:
            self._create_ib_network_view()

        ib_network = None

        try:
            ib_network = self._create_ib_network()

            # associate the network view to neutron
            dbi.associate_network_view(session,
                                       self.ib_cxt.mapping.network_view_id,
                                       network_id,
                                       subnet_id)

            self._create_ib_ip_range()
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("An exception occurred during subnet"
                                  "creation: %s"), ex)
                # deleting network deletes its child objects like ip ranges
                if ib_network:
                    self.ib_cxt.ibom.delete_network(
                        self.ib_cxt.mapping.network_view, subnet.get('cidr'))

    def _create_ib_network_view(self):
        ea_network_view = None
        ib_network_view = self.ib_cxt.ibom.create_network_view(
            self.ib_cxt.mapping.network_view, ea_network_view)
        LOG.info(_LI("Created a network view: %s"), ib_network_view)

    def _create_ib_network(self):
        session = self.ib_cxt.context.session
        network = self.ib_cxt.network
        subnet = self.ib_cxt.subnet

        network_id = network.get('id')
        is_shared = network.get('shared')
        is_external = network.get('router:external')
        cidr = subnet.get('cidr')
        gateway_ip = subnet.get('gateway_ip')

        network_template = self.grid_config.network_template

        ea_network = None

        # check if network already exists
        exists_network = self.ib_cxt.ibom.network_exists(
            self.ib_cxt.mapping.network_view, cidr)
        if exists_network:
            if is_shared or is_external:
                ib_network = self.ib_cxt.ibom.get_network(
                    self.ib_cxt.mapping.network_view, cidr)
                self.ib_cxt.ibom.update_network_options(ib_network, ea_network)
                return ib_network
            raise exc.InfobloxPrivateSubnetAlreadyExist()

        # network creation using template
        if network_template:
            ib_network = self.ib_cxt.ibom.create_network_from_template(
                self.ib_cxt.mapping.network_view, cidr, network_template)
            return ib_network

        # network creation starts
        dhcp_members = []
        nameservers = []

        relay_trel_ip = None
        if self.grid_config.dhcp_relay_management_network:
            mgmt_ip = dbi.get_management_ip(session, network_id)
            if mgmt_ip:
                relay_trel_ip = mgmt_ip.ip_address

        ib_network = self.ib_cxt.ibom.create_network(
            self.ib_cxt.mapping.network_view,
            cidr,
            nameservers=nameservers,
            dhcp_members=dhcp_members,
            gateway_ip=gateway_ip,
            relay_trel_ip=relay_trel_ip,
            extattrs=ea_network)

        for member in dhcp_members:
            self.ib_cxt.ibom.restart_all_services(member)

        return ib_network

    def _create_ib_ip_range(self):
        subnet = self.ib_cxt.subnet
        cidr = subnet.get('cidr')
        allocation_pools = subnet.get('allocation_pools')

        ea_range = None

        for ip_range in allocation_pools:
            start_ip = ip_range['start']
            end_ip = ip_range['end']
            disable = True
            self.ib_cxt.ibom.create_ip_range(
                self.ib_cxt.mapping.network_view,
                start_ip,
                end_ip,
                cidr,
                disable,
                ea_range)

    def update_subnet(self):
        pass

    def delete_subnet(self):
        session = self.ib_cxt.context.session
        subnet = self.ib_cxt.subnet
        network = self.ib_cxt.network

        network_id = network.get('id')
        is_shared = network.get('shared')
        is_external = network.get('router:external')
        subnet_id = subnet.get('id')
        cidr = subnet.get('cidr')

        subnet_deletable = ((is_shared is False and is_external is False) or
                            self.grid_config.admin_network_deletion)
        if subnet_deletable:
            self.ib_cxt.ibom.delete_network(self.ib_cxt.mapping.network_view,
                                            cidr)
            dbi.dissociate_network_view(session, network_id, subnet_id)

    def allocate_ip(self, ip_address, port_id, device_owner, device_id):
        pass

    def deallocate_ip(self, port):
        pass


class IpamAsyncController(object):

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
