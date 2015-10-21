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

from infoblox_client import connector as conn
from infoblox_client import objects
from neutron.ipam import driver
from neutron.ipam import exceptions as ipam_exc
from neutron.ipam import requests as ipam_req
from neutron.ipam import subnet_alloc
from neutron import manager

from networking_infoblox.neutron.common import config as cfg
from networking_infoblox.neutron.ipam import requests


class InfobloxPool(subnet_alloc.SubnetAllocator):
    """Infoblox Pool

    InfobloxPool is responsible for subnet management in Infoblox backend.
    """

    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet

        :param subnet_id: Neutron subnet identifier
        :returns: a InfobloxSubnet instance
        """
        network_view = 'default'
        neutron_subnet = self._fetch_subnet(self._context, subnet_id)
        subnet_request = self._request_from_subnet(neutron_subnet)
        connector = self._get_connector()

        ea = objects.EA({'Subnet ID': subnet_id})
        infoblox_network = objects.Network.search(
            connector,
            network_view=network_view,
            network=neutron_subnet['cidr'],
            search_extattrs=ea)

        if infoblox_network:
            return InfobloxSubnet(subnet_request, infoblox_network)

    @staticmethod
    def _get_connector():
        grid_id = cfg.CONF.infoblox.cloud_data_center_id
        grid_opts = cfg.get_infoblox_grid_opts(grid_id)
        # map connector opions to config
        # None as value means no name change needed
        mapping = {'host': 'grid_master_host',
                   'username': 'admin_user_name',
                   'password': 'admin_password',
                   'wapi_version': None,
                   'ssl_verify': None,
                   'http_pool_connections': None,
                   'http_pool_maxsize': None,
                   'http_request_timeout': None}
        opts = {field: grid_opts[mapping[field]]
                if mapping[field] else grid_opts[field]
                for field in mapping}
        return conn.Connector(opts)

    def _request_from_subnet(self, neutron_subnet):
        alloc_pools = None
        if neutron_subnet.get('allocation_pools'):
            alloc_pools = [netaddr.IPRange(pool['first_ip'], pool['last_ip'])
                           for pool in neutron_subnet['allocation_pools']]
        return ipam_req.SpecificSubnetRequest(
            neutron_subnet['tenant_id'],
            neutron_subnet['id'],
            neutron_subnet['cidr'],
            neutron_subnet['gateway_ip'],
            alloc_pools)

    @classmethod
    def _fetch_subnet(cls, context, id):
        plugin = manager.NeutronManager.get_plugin()
        return plugin._get_subnet(context, id)

    def allocate_subnet(self, subnet_request):
        """Create an IPAM subnet from the subnet request which contains cidr

        Makes wapi call to Infoblox NIOS to allocate subnet
        :param subnet_request: instance of SubnetRequest child
        :returns: a InfobloxSubnet instance
        """
        if self._subnetpool:
            subnet = super(InfobloxPool, self).allocate_subnet(subnet_request)
            subnet_request = subnet.get_details()

        # SubnetRequest must be an instance of SpecificSubnet
        if not isinstance(subnet_request, ipam_req.SpecificSubnetRequest):
            raise ipam_exc.InvalidSubnetRequestType(
                subnet_type=type(subnet_request))

        # Simplified for now, without creating network_view and ip_ranges
        connector = self._get_connector()
        ea = objects.EA({'Subnet ID': subnet_request.subnet_id})
        infoblox_network = objects.Network.create(
            connector,
            network_view='default',
            network=str(subnet_request.subnet_cidr),
            extattrs=ea)

        return InfobloxSubnet(subnet_request, infoblox_network)

    def update_subnet(self, subnet_request):
        """Update IPAM Subnet

        The only update subnet information the driver needs to be aware of
        are allocation pools.
        """
        pass

    def remove_subnet(self, subnet_id):
        """Remove IPAM Subnet

        Makes wapi call to remove subnet from Infoblox NIOS with all
        objects inside
        """
        network_view = 'default'
        connector = self._get_connector()

        ea = objects.EA({'Subnet ID': subnet_id})
        infoblox_network = objects.Network.search(
            connector,
            network_view=network_view,
            search_extattrs=ea)
        if infoblox_network:
            infoblox_network.delete(connector)

    def get_address_request_factory(self):
        """Returns InfobloxAddressRequestFactory"""
        return requests.InfobloxAddressRequestFactory


class InfobloxSubnet(driver.Subnet):
    """Infoblox IPAM subnet"""

    def __init__(self, subnet_details, infoblox_network):
        self._validate_subnet_data(subnet_details)
        self._subnet_details = subnet_details
        self._infoblox_network = infoblox_network

    def _validate_subnet_data(self, subnet_details):
        if not isinstance(subnet_details, ipam_req.SpecificSubnetRequest):
            raise ValueError("Subnet details should be passed"
                             " as SpecificSubnetRequest")

    def allocate(self, address_request):
        """Allocate an IP address based on the request passed in

        :param address_request: Specifies what to allocate.
        :type address_request: A subclass of AddressRequest
        :returns: A netaddr.IPAddress
        """
        # Create address with stubbed mac address, to be updated by ipam agent
        mac = ':'.join(['00'] * 6)
        connector = InfobloxPool._get_connector()
        ip = None
        if isinstance(address_request, ipam_req.SpecificAddressRequest):
            ip = str(address_request.address)
        else:
            # Ignoring allocation pools for now, just allocate from subnet
            ip = objects.IPAllocation.next_available_ip_from_cidr(
                'default', self._subnet_details.subnet_cidr)
        fa = objects.FixedAddress.create(connector,
                                         network_view='default',
                                         ip=ip,
                                         mac=mac,
                                         check_if_exists=False)
        return fa.ip

    def deallocate(self, address):
        """Deallocate previously allocated address

        :param address: The address to deallocate.
        :type address: A subclass of netaddr.IPAddress or convertible to one.
        :returns: None
        """
        connector = InfobloxPool._get_connector()
        fa = objects.FixedAddress.search(connector,
                                         network_view='default',
                                         ip=str(address))
        fa.delete()

    def get_details(self):
        """Return subnet detail as a SpecificSubnetRequest

        :returns: An instance of SpecificSubnetRequest with the subnet detail.
        """
        return self._subnet_details
