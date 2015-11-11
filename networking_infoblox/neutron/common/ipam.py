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
from oslo_utils import uuidutils

from neutron.i18n import _LE
from neutron.i18n import _LI
from neutron.ipam import exceptions as ipam_exc

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import utils
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
                LOG.exception(_LE("An exception occurred during subnet "
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

    def allocate_specific_ip(self, ip_address, mac, port_id=None,
                             device_id=None, device_owner=None):
        hostname = uuidutils.generate_uuid()
        ea_ip_address = None
        dns_view = None
        zone_auth = None

        allocated_ip = self.ib_cxt.ip_alloc.allocate_given_ip(
            self.ib_cxt.mapping.network_view,
            dns_view,
            zone_auth,
            hostname,
            mac,
            ip_address,
            ea_ip_address)
        if allocated_ip:
            LOG.debug('IP address allocated on Infoblox NIOS: %s',
                      allocated_ip)

        return allocated_ip

    def allocate_ip_from_pool(self, subnet_id, allocation_pools, mac,
                              port_id=None, device_id=None, device_owner=None):
        hostname = uuidutils.generate_uuid()
        ea_ip_address = None
        dns_view = None
        zone_auth = None
        allocated_ip = None

        for pool in allocation_pools:
            first_ip = pool['first_ip']
            last_ip = pool['last_ip']
            try:
                allocated_ip = self.ib_cxt.ip_alloc.allocate_ip_from_range(
                    self.ib_cxt.mapping.network_view,
                    dns_view,
                    zone_auth,
                    hostname,
                    mac,
                    first_ip,
                    last_ip,
                    ea_ip_address)
                if allocated_ip:
                    break
            except exc.InfobloxCannotAllocateIp:
                    LOG.debug("Failed to allocate IP from range (%s-%s)." %
                              (first_ip, last_ip))
                    continue

        if allocated_ip:
            LOG.debug('IP address allocated on Infoblox NIOS: %s',
                      allocated_ip)
        else:
            LOG.debug("All IPs from subnet %(subnet_id)s allocated",
                      {'subnet_id': subnet_id})
            raise ipam_exc.IpAddressGenerationFailure(subnet_id=subnet_id)
        return allocated_ip

    def deallocate_ip(self, ip_address):
        dns_view = None
        self.ib_cxt.ip_alloc.deallocate_ip(self.ib_cxt.mapping.network_view,
                                           dns_view,
                                           ip_address)


class IpamAsyncController(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id

    def create_network_sync(self):
        pass

    def update_network_sync(self):
        """Updates EAs for each subnet that belongs to the updated network."""
        session = self.ib_cxt.context.session
        network = self.ib_cxt.network
        network_id = network.get('id')

        subnets = dbi.get_subnets_by_network_id(session, network_id)
        for subnet in subnets:
            network_view = None
            cidr = subnet.get('cidr')
            subnet_id = subnet.get('id')

            netview_mappings = dbi.get_network_view_mappings(
                session, grid_id=self.grid_id, network_id=network_id,
                subnet_id=subnet_id)
            if netview_mappings:
                netview_row = utils.find_one_in_list(
                    'id', netview_mappings[0].network_view_id,
                    self.ib_cxt.discovered_network_views)
                network_view = netview_row.network_view

            if network_view:
                ib_network = self.ib_cxt.ibom.get_network(network_view, cidr)
                ea_network = None
                self.ib_cxt.ibom.update_network_options(ib_network, ea_network)

    def delete_network_sync(self, network_id):
        """Deletes infoblox entities that are associated with neutron network.

        db_base_plugin_v2 delete_network calls delete_subnet per subnet under
        the network so subnet deletion is not concerned here.
        """
        session = self.ib_cxt.context.session

        # delete the associated network view if not shared
        netview_mappings = dbi.get_network_view_mappings(session,
                                                         grid_id=self.grid_id,
                                                         network_id=network_id,
                                                         subnet_id=const.NONE)
        if netview_mappings:
            netview_row = utils.find_one_in_list(
                'id', netview_mappings[0].network_view_id,
                self.ib_cxt.discovered_network_views)
            if (not netview_row.shared and not self.ib_cxt.ibom.has_networks(
                    netview_row.network_view)):
                    self.ib_cxt.ibom.delete_network_view(
                        netview_row.network_view)

        # dissociate network view on network level
        dbi.dissociate_network_view(session, network_id, const.NONE)

    def create_subnet_sync(self):
        pass

    def delete_subnet_sync(self):
        pass

    def create_floatingip_sync(self, port):
        pass

    def update_floatingip_sync(self, port_id):
        pass

    def delete_floatingip_sync(self, port_id):
        pass
