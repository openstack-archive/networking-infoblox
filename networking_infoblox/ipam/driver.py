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

import functools
import netaddr
import sys

from oslo_log import log as logging
from oslo_utils import excutils

from neutron.ipam import driver
from neutron.ipam import exceptions as ipam_exc
from neutron.ipam import requests as ipam_req
from neutron.ipam import subnet_alloc
from neutron import manager

from infoblox_client import exceptions as ib_exc
from infoblox_client import objects as ib_objects

from networking_infoblox._i18n import _LE
from networking_infoblox._i18n import _LW
from networking_infoblox.ipam import requests
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context as ib_context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


def catch_ib_client_exception(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ib_exc.InfobloxException as e:
            raise exc.InfobloxClientException(msg=e), None, sys.exc_info()[2]
        except ValueError as e:
            raise exc.InfobloxValueError(msg=e), None, sys.exc_info()[2]
    return func


def rollback_wrapper(f):
    @functools.wraps(f)
    def rollback(*args, **kwargs):
        rollback_list = []
        try:
            return f(args[0], rollback_list, *args[1:], **kwargs)
        except Exception as e:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("An exception occurred during %(action)s: "
                              "%(error)s"),
                          {'action': f.__name__, 'error': e})
                for ib_object in reversed(rollback_list):
                    try:
                        ib_object.delete()
                    except ib_exc.InfobloxException as e:
                        LOG.warning(_LW("Unable to delete %(obj)s due "
                                        "to error: %(error)s."),
                                    {'obj': ib_object, 'error': e})
    return rollback


class InfobloxPool(subnet_alloc.SubnetAllocator):
    """Infoblox Pool.

    InfobloxPool is responsible for subnet management in Infoblox backend.
    """

    @catch_ib_client_exception
    def __init__(self, subnetpool, context):
        super(InfobloxPool, self).__init__(subnetpool, context)
        self._plugin = manager.NeutronManager.get_plugin()
        self._grid_manager = grid.GridManager(self._context)
        self._grid_manager.get_config()
        self._grid_config = self._grid_manager.grid_config

    @catch_ib_client_exception
    def get_subnet(self, subnet_id):
        """Retrieve an IPAM subnet.

        :param subnet_id: Neutron subnet identifier
        :returns: a InfobloxSubnet instance
        """
        neutron_subnet = self._fetch_subnet(subnet_id)
        subnet_request = self._build_request_from_subnet(neutron_subnet)

        ib_cxt = ib_context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_cxt)
        ib_network = ipam_controller.get_subnet()
        if ib_network:
            return InfobloxSubnet(subnet_request, neutron_subnet, ib_network,
                                  ib_cxt)

    @staticmethod
    def _build_request_from_subnet(neutron_subnet):
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

    @catch_ib_client_exception
    @rollback_wrapper
    def allocate_subnet(self, rollback_list, subnet_request):
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
            orig_request = {
                'name': subnet_request.name,
                'network_id': subnet_request.network_id,
                'subnetpool_id': subnet_request.subnetpool_id,
                'enable_dhcp': subnet_request.enable_dhcp,
                'dns_nameservers': subnet_request.dns_nameservers}
            subnet = super(InfobloxPool, self).allocate_subnet(subnet_request)
            subnet_request = subnet.get_details()
            subnet_request.name = orig_request['name']
            subnet_request.network_id = orig_request['network_id']
            subnet_request.subnetpool_id = orig_request['subnetpool_id']
            subnet_request.enable_dhcp = orig_request['enable_dhcp']
            subnet_request.dns_nameservers = orig_request['dns_nameservers']

        # SubnetRequest must be SpecificSubnet at this point
        if not isinstance(subnet_request, ipam_req.SpecificSubnetRequest):
            raise ipam_exc.InvalidSubnetRequestType(
                subnet_type=type(subnet_request))

        neutron_subnet = self._build_subnet_from_request(subnet_request)
        ib_cxt = ib_context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin)

        ipam_controller = ipam.IpamSyncController(ib_cxt)
        dns_controller = dns.DnsController(ib_cxt)

        ib_network = self._create_ib_network(rollback_list, ipam_controller)
        if ib_network:
            dns_controller.create_dns_zones(rollback_list)
            LOG.info("Created DNS zones.")

        return InfobloxSubnet(subnet_request, neutron_subnet, ib_network,
                              ib_cxt)

    @staticmethod
    def _build_subnet_from_request(subnet_request):
        return {'id': subnet_request.subnet_id,
                'name': subnet_request.name,
                'tenant_id': subnet_request.tenant_id,
                'network_id': subnet_request.network_id,
                'cidr': str(subnet_request.subnet_cidr),
                'ip_version': subnet_request.subnet_cidr.version,
                'subnetpool_id': subnet_request.subnetpool_id,
                'allocation_pools': subnet_request.allocation_pools,
                'gateway_ip': subnet_request.gateway_ip,
                'enable_dhcp': subnet_request.enable_dhcp,
                'dns_nameservers': subnet_request.dns_nameservers}

    @staticmethod
    def _create_ib_network(rollback_list, ipam_controller):
        ib_network = None
        retry = 1
        while True:
            try:
                LOG.info("Attempting to create ib network...")
                ib_network = ipam_controller.create_subnet(rollback_list)
                LOG.info("Successfully created ib network.")
                break
            except ib_exc.InfobloxMemberAlreadyAssigned:
                LOG.info("ib network creation failed due to member assignment "
                         "issue, tried %s time(s)", retry)
                retry += 1
                if retry > const.MEMBER_RESERVATION_RETRY:
                    raise exc.InfobloxCannotCreateSubnet(
                        reason="The grid has no more member available "
                               "to server the current subnet.")
        return ib_network

    @catch_ib_client_exception
    @rollback_wrapper
    def update_subnet(self, rollback_list, subnet_request):
        """Update IPAM Subnet.

        Updates allocation pools, dns zones, or EAs for the subnet in the
        Infoblox backend.
        """
        neutron_subnet = self._build_subnet_from_request(subnet_request)
        ib_network = self._get_ib_network(neutron_subnet['id'],
                                          neutron_subnet['ip_version'])
        if not ib_network:
            raise exc.InfobloxCannotFindSubnet(subnet_id=neutron_subnet['id'],
                                               cidr=neutron_subnet['cidr'])

        ib_cxt = ib_context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin,
            ib_network=ib_network)

        ipam_controller = ipam.IpamSyncController(ib_cxt)
        dns_controller = dns.DnsController(ib_cxt)

        ipam_controller.update_subnet_allocation_pools(rollback_list)

        if self._is_new_zone_required(neutron_subnet, ib_network):
            # subnet name is used in the domain suffix pattern and the name
            # has been changed; we need to create new zones.
            dns_controller.create_dns_zones(rollback_list)

        ipam_controller.update_subnet_details(ib_network)

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

    @catch_ib_client_exception
    def remove_subnet(self, subnet_id):
        """Remove IPAM Subnet.

        Removes a subnet from the Infoblox backend.
        """
        ib_network = self._get_ib_network(subnet_id)
        if not ib_network:
            return

        neutron_subnet = self._build_subnet_from_ib_network(ib_network)
        ib_cxt = ib_context.InfobloxContext(
            self._context,
            self._context.user_id,
            None,
            neutron_subnet,
            self._grid_config,
            plugin=self._plugin,
            ib_network=ib_network)

        ipam_controller = ipam.IpamSyncController(ib_cxt)
        dns_controller = dns.DnsController(ib_cxt)

        ipam_controller.delete_subnet(ib_network)
        dns_controller.delete_dns_zones(ib_network=ib_network)

    def _get_ib_network(self, subnet_id, ip_version=None):
        db_netviews = dbi.get_network_view_by_mapping(
            self._context.session,
            grid_id=self._grid_config.grid_id,
            subnet_id=subnet_id)
        if not db_netviews:
            return None

        network_view = db_netviews[0].network_view
        ea = ib_objects.EA({'Subnet ID': subnet_id})
        ib_network = None
        # TODO(hhwang): this should be replaced to use get_network_by_subnet_id
        # api when the following issue is resolved:
        # https://github.com/infobloxopen/infoblox-client/issues/58
        if ip_version == 4 or ip_version is None:
            ib_network = ib_objects.NetworkV4.search(
                self._grid_config.gm_connector,
                network_view=network_view,
                search_extattrs=ea)
        if ip_version == 6 or ib_network is None:
            ib_network = ib_objects.NetworkV6.search(
                self._grid_config.gm_connector,
                network_view=network_view,
                search_extattrs=ea)
        return ib_network

    @staticmethod
    def _build_subnet_from_ib_network(ib_network):
        subnet = dict()
        subnet['id'] = ib_network.extattrs.get(const.EA_SUBNET_ID)
        subnet['name'] = ib_network.extattrs.get(const.EA_SUBNET_NAME)
        subnet['network_id'] = ib_network.extattrs.get(const.EA_NETWORK_ID)
        subnet['tenant_id'] = ib_network.extattrs.get(const.EA_TENANT_ID)
        subnet['cidr'] = ib_network.network
        subnet['ip_version'] = ib_network.ip_version
        return subnet

    def get_subnet_request_factory(self):
        """Returns InfobloxSubnetRequestFactory"""
        return requests.InfobloxSubnetRequestFactory

    def get_address_request_factory(self):
        """Returns InfobloxAddressRequestFactory"""
        return requests.InfobloxAddressRequestFactory


class InfobloxSubnet(driver.Subnet):
    """Infoblox IPAM subnet."""

    def __init__(self, subnet_details, neutron_subnet, ib_network, ib_cxt):
        self._validate_subnet_data(subnet_details)
        self._subnet_details = subnet_details
        self._neutron_subnet = neutron_subnet
        self._ib_network = ib_network
        self._ib_cxt = ib_cxt

    @staticmethod
    def _validate_subnet_data(subnet_details):
        if not isinstance(subnet_details, ipam_req.SpecificSubnetRequest):
            raise ValueError("Subnet details should be passed as "
                             "SpecificSubnetRequest")

    @catch_ib_client_exception
    def allocate(self, address_request):
        """Allocate an IP address based on the request passed in.

        :param address_request: Specifies what to allocate.
        :type address_request: A subclass of AddressRequest
        :returns: A netaddr.IPAddress
        """
        ipam_controller = ipam.IpamSyncController(self._ib_cxt)
        dns_controller = dns.DnsController(self._ib_cxt)

        if isinstance(address_request, ipam_req.SpecificAddressRequest):
            allocated_ip = ipam_controller.allocate_specific_ip(
                str(address_request.address),
                address_request.mac,
                address_request.port_id,
                address_request.tenant_id,
                address_request.device_id,
                address_request.device_owner)
        else:
            allocated_ip = ipam_controller.allocate_ip_from_pool(
                self._neutron_subnet.get('id'),
                self._neutron_subnet.get('allocation_pools'),
                address_request.mac,
                address_request.port_id,
                address_request.tenant_id,
                address_request.device_id,
                address_request.device_owner)

        port_name = (address_request.port_name
                     if hasattr(address_request, 'port_name')
                     else None)
        if allocated_ip and address_request.device_owner:
            # we can deal with instance name as hostname in the ipam agent.
            instance_name = None
            try:
                dns_controller.bind_names(allocated_ip,
                                          instance_name,
                                          address_request.port_id,
                                          address_request.tenant_id,
                                          address_request.device_id,
                                          address_request.device_owner,
                                          port_name=port_name)
            except Exception:
                with excutils.save_and_reraise_exception():
                    ipam_controller.deallocate_ip(allocated_ip)

        return allocated_ip

    @catch_ib_client_exception
    def deallocate(self, address):
        """Deallocate previously allocated address.

        :param address: The address to deallocate.
        :type address: A subclass of netaddr.IPAddress or convertible to one.
        :returns: None
        """
        ip_addr = str(address)
        address_request = self._build_address_request_from_ib_address(ip_addr)
        if not address_request:
            return

        ipam_controller = ipam.IpamSyncController(self._ib_cxt)
        dns_controller = dns.DnsController(self._ib_cxt)

        ipam_controller.deallocate_ip(ip_addr)
        port_name = (address_request.port_name
                     if hasattr(address_request, 'port_name')
                     else None)
        dns_controller.unbind_names(ip_addr,
                                    None,
                                    address_request.port_id,
                                    address_request.tenant_id,
                                    address_request.device_id,
                                    address_request.device_owner,
                                    port_name)

    def _build_address_request_from_ib_address(self, ip_address):
        connector = self._ib_cxt.connector
        netview = self._ib_cxt.mapping.network_view
        dns_view = self._ib_cxt.mapping.dns_view

        ib_address = ib_objects.FixedAddress.search(connector,
                                                    network_view=netview,
                                                    ip=ip_address)
        if not ib_address:
            ib_address = ib_objects.HostRecord.search(connector,
                                                      view=dns_view,
                                                      ip=ip_address)
            if not ib_address:
                return None

        addr_req = ipam_req.AddressRequest()
        addr_req.port_id = ib_address.extattrs.get(const.EA_PORT_ID)
        addr_req.tenant_id = ib_address.extattrs.get(const.EA_TENANT_ID)
        addr_req.device_id = ib_address.extattrs.get(const.EA_PORT_DEVICE_ID)
        addr_req.device_owner = ib_address.extattrs.get(
            const.EA_PORT_DEVICE_OWNER)
        return addr_req

    def get_details(self):
        """Return subnet detail as a SpecificSubnetRequest.

        :returns: An instance of SpecificSubnetRequest with the subnet detail.
        """
        return self._subnet_details
