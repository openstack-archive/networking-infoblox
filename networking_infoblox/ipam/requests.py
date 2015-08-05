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

from neutron.common import constants as const
from neutron.ipam import requests


class RouterGatewayAddressRequest(requests.SpecificAddressRequest):
    """Used to request allocating the special router gateway address."""


class InfobloxAddressRequestFactory(requests.AddressRequestFactory):
    """Infoblox Address Request Factory

    Introduce custom address request types specific for Infoblox IPAM Driver
    """

    @classmethod
    def get_request(cls, context, port, ip_dict):
        router_port = (
            port.get('device_owner') in const.ROUTER_INTERFACE_OWNERS)
        if router_port and ip_dict.get('ip_address'):
            return RouterGatewayAddressRequest(ip_dict['ip_address'])
        else:
            return super(InfobloxAddressRequestFactory, cls).get_request(
                context, port, ip_dict)
