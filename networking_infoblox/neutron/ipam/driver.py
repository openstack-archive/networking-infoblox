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

from neutron.ipam import driver

from networking_infoblox.neutron.ipam import requests


class InfobloxPool(driver.Pool):
    """Infoblox Pool

    InfobloxPool is responsible for subnet management in Infoblox backend.
    """

    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet

        :param subnet_id: Neutron subnet identifier
        :returns: a InfobloxSubnet instance
        """
        return InfobloxSubnet()

    def allocate_subnet(self, subnet_request):
        """Create an IPAM subnet from the subnet request which contains cidr

        Makes wapi call to Infoblox NIOS to allocate subnet
        :param subnet_request: instance of SubnetRequest child
        :returns: a InfobloxSubnet instance
        """
        return InfobloxSubnet()

    def update_subnet(self, subnet_request):
        """Update IPAM Subnet

        The only update subnet information the driver needs to be aware of
        are allocation pools.
        """
        pass

    def remove_subnet(self, subnet):
        """Remove IPAM Subnet

        Makes wapi call to remove subnet from Infoblox NIOS with all
        objects inside
        """
        pass

    def get_address_request_factory(self):
        """Returns InfobloxAddressRequestFactory"""
        return requests.InfobloxAddressRequestFactory


class InfobloxSubnet(driver.Subnet):
    """Infoblox IPAM subnet"""

    def allocate(self, address_request):
        """Allocate an IP address based on the request passed in

        :param address_request: Specifies what to allocate.
        :type address_request: A subclass of AddressRequest
        :returns: A netaddr.IPAddress
        """
        pass

    def deallocate(self, address):
        """Deallocate previously allocated address

        :param address: The address to deallocate.
        :type address: A subclass of netaddr.IPAddress or convertible to one.
        :returns: None
        """
        pass

    def get_details(self):
        """Return subnet detail as a SpecificSubnetRequest

        :returns: An instance of SpecificSubnetRequest with the subnet detail.
        """
        pass
