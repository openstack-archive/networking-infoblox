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

from neutron.ipam.drivers.neutrondb_ipam import driver as neutron_ipam


LOG = logging.getLogger(__name__)


class InfobloxSubnet(neutron_ipam.NeutronDbSubnet):
    """Manage IP addresses for Infoblox IPAM driver.

    """
    def __init__(self, internal_id, ctx, cidr=None,
                 allocation_pools=None, gateway_ip=None, tenant_id=None,
                 subnet_id=None, subnet_id_not_set=False):
        super(InfobloxSubnet, self).__init__()

    def allocate(self, address_request):
        ip_address = super(InfobloxSubnet, self).allocate(address_request)
        return ip_address

    def deallocate(self, address):
        super(InfobloxSubnet, self).deallocate(address)

    def update_allocation_pools(self, pools):
        super(InfobloxSubnet, self).update_allocation_pools(pools)

    def get_details(self):
        """Return subnet data as a SpecificSubnetRequest"""
        super(InfobloxSubnet, self).get_details()

    def associate_neutron_subnet(self, subnet_id):
        """Set neutron identifier for this subnet"""
        super(InfobloxSubnet, self).associate_neutron_subnet(subnet_id)


class InfobloxPool(neutron_ipam.NeutronDbPool):
    """Subnet pools backed by Neutron.
    """

    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet.

        :param subnet_id: Neutron subnet identifier
        :returns: a NeutronDbSubnet instance
        """
        subnet = super(InfobloxPool, self).get_subnet(subnet_id)
        return subnet

    def allocate_subnet(self, subnet_request):
        """Create an IPAMSubnet object for the provided cidr.

        This method does not actually do any operation in the driver, given
        its simplified nature.

        :param cidr: subnet's CIDR
        :returns: a NeutronDbSubnet instance
        """
        #session = self._context.session
        #import pdb; pdb.set_trace()
        # LOG.info("HSH ==============> allocate_subnet > subnet_request: %s",
        #          subnet_request.__dict__)
        # { '_subnet_cidr': IPNetwork('11.11.0.0/27'),
        #   '_subnet_id': 'ba771d0c-6d03-48a0-bc2a-dd00a848519a',
        #   '_tenant_id': u'05aa8cb6aa4a4c1bb9dbeb83fa2609aa',
        #   '_allocation_pools': [IPRange('11.11.0.2', '11.11.0.30')],
        #   '_gateway_ip': IPAddress('11.11.0.1')
        # }
        # LOG.info("HSH ==============> allocate_subnet > subnet_id: %s",
        #          subnet_request.subnet_id)

        subnet = super(InfobloxPool, self).allocate_subnet(subnet_request)
        # LOG.info("HSH ==============> allocate_subnet > subnet: %s",
        #          subnet.__dict__)
        # { '_cidr': IPNetwork('11.11.0.0/27'),
        #   'subnet_manager': <neutron.ipam.drivers.neutrondb_ipam.db_api.
        #              IpamSubnetManager object at 0x7f50cef54590>,
        #   '_tenant_id': u'05aa8cb6aa4a4c1bb9dbeb83fa2609aa',
        #   '_context': <neutron.context.Context object at 0x7f50cef808d0>,
        #   '_subnet_id': None,
        #   '_pools': [IPRange('11.11.0.2', '11.11.0.30')],
        #   '_gateway_ip': IPAddress('11.11.0.1')
        # }
        return subnet

    def update_subnet(self, subnet_request):
        """Update subnet info the in the IPAM driver.

        The only update subnet information the driver needs to be aware of
        are allocation pools.
        """

        subnet = super(InfobloxPool, self).update_subnet(subnet_request)
        return subnet

    def remove_subnet(self, subnet):
        """Remove data structures for a given subnet.
        """

        super(InfobloxPool, self).remove_subnet(subnet)
