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


class InfobloxPool(driver.Pool):
    """Infoblox IPAM Driver

    IPAM Driver is responsible for autoritative creating subnets and
    ip address allocation on Infoblox NIOS using wapi calls.
    """

    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet

        :param subnet_id: Neutron subnet identifier
        :returns: a InfobloxSubnet instance
        """
        return InfobloxSubnet()

    def allocate_subnet(self, subnet_request):
        """Create an IPAM Subnet object for the provided cidr

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


class InfobloxSubnet(driver.Subnet):
    """Infoblox IPAM subnet"""

    def allocate(self, address_request):
        """Allocates an IP address based on the request passed in

        :param address_request: Specifies what to allocate.
        :type address_request: An instance of a subclass of AddressRequest
        :returns: A netaddr.IPAddress
        """
        pass

    def deallocate(self, address):
        """Returns a previously allocated address to the pool

        :param address: The address to give back.
        :type address: A netaddr.IPAddress or convertible to one.
        :returns: None
        """
        pass

    def get_details(self):
        """Returns the details of the subnet

        :returns: An instance of SpecificSubnetRequest with the subnet detail.
        """
        pass
