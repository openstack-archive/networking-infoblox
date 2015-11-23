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

from oslo_config import cfg
from oslo_utils import uuidutils

from neutron.api.v2 import attributes
from neutron.db import address_scope_db


DB_PLUGIN_KLASS = 'neutron.db.db_base_plugin_v2.NeutronDbPluginV2'


class NeutronPluginStub(object):

    def __init__(self, context, plugin):
        self.context = context
        self.plugin = plugin

        cfg.CONF.set_override('notify_nova_on_port_data_changes', False)
        cfg.CONF.set_override('notify_nova_on_port_status_changes', False)
        cfg.CONF.set_override('allow_overlapping_ips', True)

    def create_network(self, tenant_id, name, shared=False,
                       admin_state_up=True):
        network = {'network': {'name': name,
                               'shared': shared,
                               'admin_state_up': admin_state_up,
                               'tenant_id': tenant_id}}
        return self.plugin.create_network(self.context, network)

    def create_subnet(self, tenant_id, name, network_id, cidr, ip_version=4,
                      enable_dhcp=True, subnetpool_id=None,
                      v6_address_mode=attributes.ATTR_NOT_SPECIFIED,
                      allocation_pools=attributes.ATTR_NOT_SPECIFIED):
        subnet = {'subnet': {'name': name,
                             'cidr': cidr,
                             'ip_version': ip_version,
                             'gateway_ip': attributes.ATTR_NOT_SPECIFIED,
                             'allocation_pools': allocation_pools,
                             'enable_dhcp': enable_dhcp,
                             'dns_nameservers': attributes.ATTR_NOT_SPECIFIED,
                             'host_routes': attributes.ATTR_NOT_SPECIFIED,
                             'ipv6_address_mode': v6_address_mode,
                             'ipv6_ra_mode': attributes.ATTR_NOT_SPECIFIED,
                             'network_id': network_id,
                             'tenant_id': tenant_id,
                             'subnetpool_id': subnetpool_id}}
        return self.plugin.create_subnet(self.context, subnet)

    def create_subnet_pool(self, tenant_id, name, prefix_list, min_prefixlen,
                           ip_version, shared=False,
                           max_prefixlen=attributes.ATTR_NOT_SPECIFIED,
                           default_prefixlen=attributes.ATTR_NOT_SPECIFIED,
                           default_quota=attributes.ATTR_NOT_SPECIFIED):
        subnetpool = {'subnetpool': {'name': name,
                                     'tenant_id': tenant_id,
                                     'prefixes': prefix_list,
                                     'min_prefixlen': min_prefixlen,
                                     'max_prefixlen': max_prefixlen,
                                     'default_prefixlen': default_prefixlen,
                                     'shared': shared,
                                     'default_quota': default_quota}}
        return self.plugin.create_subnetpool(self.context, subnetpool)

    def create_address_scope(self, tenant_id, name, shared=False):
        address_scope = {'address_scope': {'id': uuidutils.generate_uuid(),
                                           'tenant_id': tenant_id,
                                           'name': name,
                                           'shared': shared}}
        return address_scope_db.create_address_scope(self.context,
                                                     address_scope)
