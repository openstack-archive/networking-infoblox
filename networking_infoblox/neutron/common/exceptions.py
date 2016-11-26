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

from neutron_lib import exceptions

from networking_infoblox._i18n import _


class InfobloxNeutronException(exceptions.NeutronException):
    """Generic Infoblox Exception."""
    def __init__(self, response, **kwargs):
        self.response = response
        super(InfobloxNeutronException, self).__init__(**kwargs)


class InfobloxInvalidCloudDataCenter(exceptions.NeutronException):
    message = _("Invalid cloud data center: '%(data_center_id)s'")


class InfobloxCannotFindMember(exceptions.NeutronException):
    message = _("Cannot find the member: '%(member)s'")


class InfobloxCannotReserveAuthorityMember(exceptions.NeutronException):
    message = _("Cannot reserve the authority member for network view: "
                "%(network_view)s")


class InfobloxAuthorityMemberNotReserved(exceptions.NeutronException):
    message = _("Authority member is not reserved for network view: "
                "%(network_view)s")


class InfobloxDHCPMemberNotReserved(exceptions.NeutronException):
    message = _("DHCP member is not reserved for network view: "
                "(%(network_view)s), cidr (%(cidr)s)")


class InfobloxDNSMemberNotReserved(exceptions.NeutronException):
    message = _("DNS member is not reserved for network view "
                "(%(network_view)s), cidr (%(cidr)s)")


class InfobloxNetworkViewMappingNotFound(exceptions.NeutronException):
    message = _("Cannot find a network view mapped for subnet %(subnet_id)s")


class MultipleNetworkViewMappingFound(exceptions.Conflict):
    message = _("Multiple network view mapping found. You need to add more "
                "filters to narrow down the search")


class InfobloxNetworkViewNotFound(exceptions.NeutronException):
    message = _("Network view '%(network_view)s' does not exist.")


class InfobloxNetworkViewNotParticipated(exceptions.NeutronException):
    message = _("Network view '%(network_view)s' found but not participated.")


class InfobloxDefaultNetworkViewNotFound(exceptions.NeutronException):
    message = _("No default network view exists.")


class InfobloxCannotCreateSubnet(exceptions.NeutronException):
    message = _("Cannot create a subnet because %(reason)s")


class InfobloxCannotFindSubnet(exceptions.NeutronException):
    message = _("Cannot find the subnet %(subnet_id)s for %(cidr)s from NIOS")


class InfobloxPrivateSubnetAlreadyExist(exceptions.Conflict):
    message = _("Network with the same CIDR already exists on NIOS.")


class InfobloxCannotAllocateIp(exceptions.NeutronException):
    message = _("Cannot allocate IP %(ip_data)s")


class InfobloxCannotFindFixedIp(exceptions.NeutronException):
    message = _("Cannot find the fixed IP %(ip)s")


class InfobloxClientException(exceptions.NeutronException):
    message = _("InfobloxClientException '%(msg)s'")


class InfobloxValueError(exceptions.NeutronException):
    message = _("InfobloxValueError '%(msg)s' "
                "Refer to neutron log for more detail")
