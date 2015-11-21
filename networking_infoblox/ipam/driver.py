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

import netaddr

from oslo_log import log as logging

from neutron.ipam import driver
from neutron.ipam import exceptions as ipam_exc
from neutron.ipam import requests as ipam_req
from neutron.ipam import subnet_alloc
from neutron import manager

from infoblox_client import objects as ib_objects

from networking_infoblox.ipam import requests
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class InfobloxPool(subnet_alloc.SubnetAllocator):
    """Infoblox Pool.

    InfobloxPool is responsible for subnet management in Infoblox backend.
    """

    def __init__(self, *args, **kwargs):
        super(InfobloxPool, self).__init__(*args, **kwargs)
        self._plugin = manager.NeutronManager.get_plugin()
        self._grid_manager = grid.GridManager(self._context)
        self._grid_manager.get_config()
        self._grid_config = self._grid_manager.grid_config

    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet.

        :param subnet_id: Neutron subnet identifier
        :returns: a InfobloxSubnet instance
        """
        neutron_subnet = self._fetch_subnet(subnet_id)
        subnet_request = self._build_request_from_subnet(neutron_subnet)

        ib_context = context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_context)
        ib_network = ipam_controller.get_subnet()
        if ib_network:
            return InfobloxSubnet(subnet_request, ib_network)

    def _build_request_from_subnet(self, neutron_subnet):
        alloc_pools = None
        if neutron_subnet.get('allocation_pools'):
            alloc_pools = [netaddr.IPRange(pool['start'], pool['end'])
                           for pool in neutron_subnet['allocation_pools']]
        return ipam_req.SpecificSubnetRequest(
            neutron_subnet['tenant_id'],
            neutron_subnet['id'],
            neutron_subnet['cidr'],
            neutron_subnet['gateway_ip'],
            alloc_pools)

    def _fetch_subnet(self, subnet_id):
        return self._plugin.get_subnet(self._context, subnet_id)

    def allocate_subnet(self, subnet_request):
        """Create an IPAM subnet from the subnet request which contains cidr.

        Allocates a subnet to the Infoblox backend.
        :param subnet_request: instance of SubnetRequest child
        :returns: a InfobloxSubnet instance
        """
        # if subnetpool is defined, the request is AnySubnetRequest, so
        # we need to convert it to SpecificSubnetRequest calling
        # SubnetAllocator; however, calling this will not pass custom
        # parameters we defined so we need to get them back from the original
        # subnet_request.
        if self._subnetpool:
            request_cache = {
                'name': subnet_request.name,
                'network_id': subnet_request.network_id,
                'subnetpool_id': subnet_request.subnetpool_id,
                'enable_dhcp': subnet_request.enable_dhcp}
            subnet = super(InfobloxPool, self).allocate_subnet(subnet_request)
            subnet_request = subnet.get_details()
            subnet_request.name = request_cache['name']
            subnet_request.network_id = request_cache['network_id']
            subnet_request.subnetpool_id = request_cache['subnetpool_id']
            subnet_request.enable_dhcp = request_cache['enable_dhcp']

        # SubnetRequest must be SpecificSubnet at this point
        if not isinstance(subnet_request, ipam_req.SpecificSubnetRequest):
            raise ipam_exc.InvalidSubnetRequestType(
                subnet_type=type(subnet_request))

        neutron_subnet = self._build_subnet_from_request(subnet_request)
        ib_context = context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_context)
        dns_controller = dns.DnsController(ib_context)

        ib_network = ipam_controller.create_subnet()
        dns_controller.create_dns_zones()

        return InfobloxSubnet(subnet_request, ib_network)

    def _build_subnet_from_request(self, subnet_request):
        return {'id': subnet_request.subnet_id,
                'name': subnet_request.name,
                'tenant_id': subnet_request.tenant_id,
                'network_id': subnet_request.network_id,
                'cidr': str(subnet_request.subnet_cidr),
                'ip_version': subnet_request.subnet_cidr.version,
                'subnetpool_id': subnet_request.subnetpool_id,
                'allocation_pools': subnet_request.allocation_pools,
                'gateway_ip': subnet_request.gateway_ip,
                'enable_dhcp': subnet_request.enable_dhcp}

    def update_subnet(self, subnet_request):
        """Update IPAM Subnet.

        Updates allocation pools, dns zones, or EAs for the subnet in the
        Infoblox backend.
        """
        neutron_subnet = self._build_subnet_from_request(subnet_request)
        ib_context = context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_context)
        dns_controller = dns.DnsController(ib_context)

        ipam_controller.update_subnet_allocation_pools()

        ib_network = ipam_controller.get_subnet()
        if self._is_new_zone_required(neutron_subnet, ib_network):
            # subnet name is used in the domain suffix pattern and the name
            # has been changed; thus we need to delete the existing dns zones
            # and create new zones.
            old_dns_zone = dns_controller.pattern_builder.get_zone_name(
                ib_network.extattrs.get(const.EA_SUBNET_NAME))
            dns_controller.delete_dns_zones(old_dns_zone)
            dns_controller.create_dns_zones()

        ipam_controller.update_subnet_eas(ib_network)

    def _is_new_zone_required(self, subnet, ib_network):
        pattern = self._grid_config.default_domain_name_pattern
        subnet_used = '{subnet_name}' in pattern
        if subnet_used:
            new_subnet_name = subnet.get('name')
            old_subnet_name = ib_network.extattrs.get(const.EA_SUBNET_NAME)
            return (old_subnet_name is not None and
                    new_subnet_name is not None and
                    old_subnet_name != new_subnet_name)
        return False

    def remove_subnet(self, subnet_id):
        """Remove IPAM Subnet.

        Removes a subnet from the Infoblox backend.
        """
        ib_network = self._get_ib_network(subnet_id)
        if not ib_network:
            return

        neutron_subnet = self._build_subnet_from_ib_network(ib_network)
        ib_context = context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_context)
        dns_controller = dns.DnsController(ib_context)

        ipam_controller.delete_subnet()
        dns_controller.delete_dns_zones()

    def _get_ib_network(self, subnet_id):
        db_netviews = dbi.get_network_view_by_mapping(
            self._context.session,
            grid_id=self._grid_config.grid_id,
            subnet_id=subnet_id)
        if not db_netviews:
            raise exc.InfobloxNetworkViewMappingNotFound(subnet_id=subnet_id)

        network_view = db_netviews[0].network_view
        ea = ib_objects.EA({'Subnet ID': subnet_id})

        ib_network = ib_objects.Network.search(
            self._grid_config.gm_connector,
            network_view=network_view,
            search_extattrs=ea)
        return ib_network

    def _build_subnet_from_ib_network(self, ib_network):
        subnet = dict()
        subnet['id'] = ib_network.extattrs.get(const.EA_SUBNET_ID)
        subnet['name'] = ib_network.extattrs.get(const.EA_SUBNET_NAME)
        subnet['network_id'] = ib_network.extattrs.get(const.EA_NETWORK_ID)
        subnet['tenant_id'] = ib_network.extattrs.get(const.EA_TENANT_ID)
        subnet['cidr'] = ib_network.network
        return subnet

    def get_subnet_request_factory(self):
        """Returns InfobloxSubnetRequestFactory"""
        return requests.InfobloxSubnetRequestFactory

    def get_address_request_factory(self):
        """Returns InfobloxAddressRequestFactory"""
        return requests.InfobloxAddressRequestFactory


class InfobloxSubnet(driver.Subnet):
    """Infoblox IPAM subnet."""

    def __init__(self, subnet_details, infoblox_network):
        self._validate_subnet_data(subnet_details)
        self._subnet_details = subnet_details
        self._infoblox_network = infoblox_network
        self._conn = utils.get_connector()

    def _validate_subnet_data(self, subnet_details):
        if not isinstance(subnet_details, ipam_req.SpecificSubnetRequest):
            raise ValueError("Subnet details should be passed"
                             " as SpecificSubnetRequest")

    def allocate(self, address_request):
        """Allocate an IP address based on the request passed in.

        :param address_request: Specifies what to allocate.
        :type address_request: A subclass of AddressRequest
        :returns: A netaddr.IPAddress
        """
        if isinstance(address_request, ipam_req.SpecificAddressRequest):
            ip = str(address_request.address)
            fa = self._allocate_fixed_ip(ip)
        else:
            fa = self._allocate_ip_from_subnet_pools()
        return fa.ip

    def _allocate_fixed_ip(self, ip):
        # Create address with stubbed mac address, to be updated by ipam agent
        mac = ':'.join(['00'] * 6)
        return ib_objects.FixedAddress.create(self._conn,
                                              network_view='default',
                                              ip=ip,
                                              mac=mac,
                                              check_if_exists=False)

    def _allocate_ip_from_subnet_pools(self):
        cidr = self._infoblox_network.network
        pools = ib_objects.IPRange.search_all(self._conn,
                                              network_view='default',
                                              network=cidr)
        for pool in pools:
            try:
                ip_req = ib_objects.IPAllocation.next_available_ip_from_range(
                    'default', pool.start_addr, pool.end_addr)
                return self._allocate_fixed_ip(ip_req)
            except Exception:
                continue
        raise ipam_exc.IpAddressGenerationFailure(
            subnet_id=self._subnet_details.subnet_id)

    def deallocate(self, address):
        """Deallocate previously allocated address.

        :param address: The address to deallocate.
        :type address: A subclass of netaddr.IPAddress or convertible to one.
        :returns: None
        """
        fa = ib_objects.FixedAddress.search(self._conn,
                                            network_view='default',
                                            ip=str(address))
        fa.delete()

    def get_details(self):
        """Return subnet detail as a SpecificSubnetRequest.

        :returns: An instance of SpecificSubnetRequest with the subnet detail.
        """
        return self._subnet_details
