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

from neutron.common import exceptions


class InfobloxNeutronException(exceptions.NeutronException):
    """Generic Infoblox Exception."""
    def __init__(self, response, **kwargs):
        self.response = response
        super(InfobloxNeutronException, self).__init__(**kwargs)


class InfobloxInvalidCloudDataCenter(exceptions.NeutronException):
    message = ("Invalid cloud data center: '%(data_center_id)s'")


class InfobloxCannotFindMember(exceptions.NeutronException):
    message = ("Cannot find the member: '%(member)s'")


class InfobloxCannotReserveAuthorityMember(exceptions.NeutronException):
    message = ("Cannot reserve the authority member for network view: "
               "%s(network_view)s")


class InfobloxPrivateSubnetAlreadyExist(exceptions.Conflict):
    message = ("Network with the same CIDR already exists on NIOS.")
