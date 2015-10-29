# Copyright 2015 OpenStack LLC.
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

from neutron.common import constants as n_const

from infoblox_client import exceptions as ibc_exc

from networking_infoblox.neutron.common import constants as const


LOG = logging.getLogger(__name__)


class PatternBuilder(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config

    def get_hostname(self, port, ip_address, instance_name=None):
        default_pattern = self.grid_config.default_host_name_pattern
        port_owner = port['device_owner']

        if (port_owner == n_const.DEVICE_OWNER_FLOATINGIP and
                instance_name and "{instance_name}" in default_pattern):
                hostname_pattern = default_pattern
        elif port_owner in const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP.keys():
            hostname_pattern = (
                const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP[port_owner])
        else:
            hostname_pattern = default_pattern

        pattern = [hostname_pattern,
                   self.grid_config.default_domain_name_pattern]
        pattern = '.'.join([el.strip('.') for el in pattern if el])
        return self._build(pattern, port, ip_address, instance_name)

    def get_zone_name(self):
        return self._build(self.grid_config.default_domain_name_pattern)

    def _build(self, pattern, port=None, ip_address=None, instance_name=None):
        self._validate_pattern(pattern)

        subnet = self.ib_cxt.subnet
        network = self.ib_cxt.network
        subnet_name = subnet['name'] if subnet.get('name') else subnet['id']
        network_name = (network['name'] if network.get('name')
                        else network['id'])

        pattern_dict = {
            'network_id': subnet['network_id'],
            'network_name': network_name,
            'tenant_id': subnet['tenant_id'],
            'subnet_name': subnet_name,
            'subnet_id': subnet['id']
        }

        if port:
            pattern_dict['port_id'] = port['id']
            pattern_dict['instance_id'] = port['device_id']
            if instance_name:
                pattern_dict['instance_name'] = instance_name

        if ip_address:
            octets = ip_address.split('.')
            ip_addr = ip_address.replace('.', '-').replace(':', '-')
            pattern_dict['ip_address'] = ip_addr
            for i in range(len(octets)):
                octet_key = 'ip_address_octet{i}'.format(i=(i + 1))
                pattern_dict[octet_key] = octets[i]

        try:
            fqdn = pattern.format(**pattern_dict)
        except (KeyError, IndexError) as e:
            raise ibc_exc.InfobloxConfigException(
                msg="Invalid pattern %s" % e)
        return fqdn

    @staticmethod
    def _validate_pattern(pattern):
        invalid_values = ['..']
        for val in invalid_values:
            if val in pattern:
                error_message = "Invalid pattern value {0}".format(val)
                raise ibc_exc.InfobloxConfigException(msg=error_message)
