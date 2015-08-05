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

#import re

from oslo_log import log as logging
from oslo_utils import excutils

#from neutron.common import ipv6_utils
#from neutron.ipam.drivers.infoblox.common import config as ib_conf
from neutron.ipam.drivers.infoblox.common import constants as ib_const
from neutron.ipam.drivers.infoblox.common import eam
from neutron.ipam.drivers.infoblox.common import exceptions as ib_exc
from neutron.ipam.drivers.infoblox.common import utils as ib_utils
#from neutron.ipam.drivers.infoblox.db import db_api as ib_dbi


LOG = logging.getLogger(__name__)


class DnsDriver(object):

    def __init__(self, ipam_manager):
        self.ipam = ipam_manager

    def create_dns_zones(self):
        #session = self.ipam.context.session
        #user_id = self.ipam.user_id
        network = self.ipam.network
        subnet = self.ipam.subnet
        tenant_id = subnet.get('tenant_id')
        #network_id = subnet.get('network_id')
        #subnet_id = subnet.get('id')
        subnet_name = subnet.get('name')
        cidr = subnet.get('cidr')
        network_view = self.ipam.condition.network_view
        dns_view = self.ipam.condition.dns_view

        # for GM, GM itself has to be added to the grid primary for dns
        # so that both dns and dhcp have the same parent in order for
        # host record to work when dhcp network is non-delegated.
        # when the network view belongs to GM but a dhcp network is delegated
        # to a member, dns member must be the dhcp member so that it has the
        # same parent.
        dns_members = self.ipam.condition.dns_members
        network_members = self.ipam.condition.network_members
        if network_members[0].member_type == ib_const.MEMBER_TYPE_GRID_MASTER:
            dns_members['primary'] = network_members + dns_members['primary']

        # create dns view
        self.ipam.ibom.create_dns_view(network_view, dns_view)

        zone_ea = eam.get_ea_for_zone(self.ipam.user_id, tenant_id, network)

        dns_zone = self.ipam.condition.pattern_builder.build_zone_name(
            network, subnet)
        prefix = ib_utils.get_prefix_for_dns_zone(subnet_name, cidr)

        try:
            ns_group = self.ipam.condition.ns_group
            zone_format = 'IPV%s' % subnet['ip_version']

            if ns_group:
                self.ipam.ibom.create_dns_zone(dns_view,
                                               dns_zone=dns_zone,
                                               ns_group=ns_group,
                                               extattrs=zone_ea)
                self.ipam.ibom.create_dns_zone(dns_view,
                                               dns_zone=cidr,
                                               prefix=prefix,
                                               zone_format=zone_format,
                                               extattrs=zone_ea)
            else:
                dns_primary = dns_members['primary']
                dns_secondary = dns_members['secondary']
                self.ipam.ibom.create_dns_zone(
                    dns_view,
                    dns_zone=dns_zone,
                    primary_dns_members=dns_primary,
                    secondary_dns_members=dns_secondary,
                    extattrs=zone_ea)
                self.ipam.ibom.create_dns_zone(
                    dns_view,
                    dns_zone=cidr,
                    primary_dns_members=dns_primary,
                    prefix=prefix,
                    zone_format=zone_format,
                    extattrs=zone_ea)
        except ib_exc:
            with excutils.save_and_reraise_exception():
                pass
                # handle rollback here

    def delete_dns_zones(self, context, subnet):
        pass

    #  def bind_names(self, condition, dns_members, subnet, port, port_ea):
    #      if not port['device_owner']:
    #          return
    #
    #      try:
    #          self._bind_names(condition,
    #                           dns_members,
    #                           subnet,
    #                           port,
    #                           self.ip_allocator.default.bind_names,
    #                           port_ea)
    #      except ib_exc.InfobloxCannotCreateObject as ex:
    #          #self.unbind_names(port)
    #          raise ex
    #
    #  def unbind_names(self, condition, dns_members, subnet, port):
    #      self._bind_names(condition, dns_members, subnet, port,
    #                       self.ip_allocator.default.unbind_names)
    #
    # def _bind_names(self, condition, dns_members, subnet, port, binding_func,
    #                 port_ea=None):
    #      all_dns_members = []
    #
    #      for ip in port['fixed_ips']:
    #          if subnet['ip_version'] == 4 or \
    #                  not ipv6_utils.is_auto_address_subnet(subnet):
    #              #cfg = self.config_finder.find_config_for_subnet(context,
    #                                                               subnet)
    #              #dns_members = cfg.reserve_dns_members()
    #              all_dns_members.extend(dns_members)
    #              ip_addr = ip['ip_address']
    #              instance_name = self.get_instancename(port_ea)
    #
    #              #condition.pattern_builder.get_hostname_pattern(port,
    #                                                              condition)
    #              #hostname_pattern = self.get_hostname_pattern(port, cfg)
    #              #pattern_builder = self.pattern_builder(
    #                   hostname_pattern, cfg.domain_suffix_pattern)
    #              #fqdn = pattern_builder.build(
    #              #    context, subnet, port, ip_addr, instance_name)
    #
    #              #binding_func(condition.network_view, cfg.dns_view,
    #                   ip_addr, fqdn, port_ea)
    #
    #      for member in set(all_dns_members):
    #          self.infoblox.restart_all_services(member)
