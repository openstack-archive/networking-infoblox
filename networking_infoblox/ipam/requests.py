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

from neutron.common import constants as n_const
from neutron.ipam import requests


class InfobloxFixedAddressRequest(requests.SpecificAddressRequest):

    def __init__(self, address, mac, port_id, device_id, device_owner):
        super(InfobloxFixedAddressRequest, self).__init__(address)
        self.mac = mac
        self.port_id = port_id
        self.device_id = device_id
        self.device_owner = device_owner


class InfobloxFloatingAddressRequest(InfobloxFixedAddressRequest):
    """Used to request allocating the floating ip address."""


class InfobloxRouterGatewayAddressRequest(InfobloxFixedAddressRequest):
    """Used to request allocating the special router gateway address."""


class InfobloxDhcpPortAddressRequest(InfobloxFixedAddressRequest):
    """Used to request allocating the dhcp port address."""


class InfobloxAnyAddressRequest(requests.AnyAddressRequest):
    """Used to request allocating any address from subnet."""

    def __init__(self, mac, port_id, device_id, device_owner):
        super(InfobloxAnyAddressRequest, self).__init__()
        self.mac = mac
        self.port_id = port_id
        self.device_id = device_id
        self.device_owner = device_owner


class InfobloxAutomaticAddressRequest(requests.AutomaticAddressRequest):
    """Used to request automatic address for auto-addressed subnets."""

    def __init__(self, mac, port_id, device_id, device_owner, prefix):
        super(InfobloxAutomaticAddressRequest, self).__init__(prefix=prefix,
                                                              mac=mac)
        self.mac = mac
        self.port_id = port_id
        self.device_id = device_id
        self.device_owner = device_owner


class InfobloxAddressRequestFactory(requests.AddressRequestFactory):
    """Infoblox Address Request Factory.

    Introduce custom address request types specific for Infoblox IPAM Driver
    """

    @classmethod
    def get_request(cls, context, port, ip_dict):
        if ip_dict.get('ip_address'):
            if port['device_owner'] == n_const.DEVICE_OWNER_DHCP:
                request_class = InfobloxDhcpPortAddressRequest
            elif port['device_owner'] == n_const.DEVICE_OWNER_ROUTER_GW:
                request_class = InfobloxRouterGatewayAddressRequest
            elif port['device_owner'] == n_const.DEVICE_OWNER_FLOATINGIP:
                request_class = InfobloxFloatingAddressRequest
            else:
                request_class = InfobloxFixedAddressRequest
            return request_class(ip_dict['ip_address'],
                                 port['mac_address'],
                                 port['port_id'],
                                 port['device_id'],
                                 port['device_owner'])
        elif ip_dict.get('eui64_address'):
            return InfobloxAutomaticAddressRequest(
                port['mac_address'],
                port['port_id'],
                port['device_id'],
                port['device_owner'],
                ip_dict['subnet_cidr'])
        else:
            return InfobloxAnyAddressRequest(port['mac_address'],
                                             port['port_id'],
                                             port['device_id'],
                                             port['device_owner'])
