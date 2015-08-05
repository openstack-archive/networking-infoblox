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
#from oslo_serialization import jsonutils
from oslo_utils import excutils
from oslo_utils import uuidutils

from neutron.ipam.drivers.infoblox.common import config as ib_conf
#from neutron.ipam.drivers.infoblox.common import constants as ib_const
from neutron.ipam.drivers.infoblox.common import eam
#from neutron.ipam.drivers.infoblox.common import exceptions as ib_exc
from neutron.ipam.drivers.infoblox.common import utils as ib_utils
from neutron.ipam.drivers.infoblox.db import db_api as ib_dbi


LOG = logging.getLogger(__name__)


class DhcpDriver(object):

    def __init__(self, ipam_manager):
        self.ipam = ipam_manager

    def create_network(self):
        pass

    def create_network_sync(self):
        if not ib_conf.CONF_IPAM.dhcp_relay_management_network:
            LOG.info(_('dhcp_relay_management_network option is not set in '
                       'config. DHCP will be used for management network '
                       'interface.'))
            return

        session = self.ipam.context.session
        user_id = self.ipam.user_id
        network = self.ipam.network
        network_id = network.get('id')
        tenant_id = network.get('tenant_id')

        # adds management ip
        mgmt_net_cidr = ib_conf.CONF_IPAM.dhcp_relay_management_network
        mgmt_net_view = ib_conf.CONF_IPAM.dhcp_relay_management_network_view
        mac = ':'.join(['00'] * 6)

        # if IP is allocated for DHCP relay (trel interface)
        # when DHCP relay management network is set,
        # OpenStack is unaware of this so no port to associate with.
        # in this case, we still need to populate EAs with default values.
        ip_ea = eam.get_default_ea_for_ip(user_id, tenant_id)

        fixed_address = self.ipam.ibom.create_fixed_address_from_cidr(
            mgmt_net_view, mac, mgmt_net_cidr, ip_ea)
        ip_version = ib_utils.get_ip_version(fixed_address.ip)

        ib_dbi.add_management_ip(session, network_id, fixed_address.ip,
                                 ip_version, fixed_address.ref)

    def update_network(self):
        pass

    def update_network_sync(self):
        """Update EAs for each subnet that belong to the updated network.
        """
        session = self.ipam.context.session
        user_id = self.ipam.user_id
        network = self.ipam.network
        network_id = network.get('id')
        tenant_id = network.get('tenant_id')

        subnets = ib_dbi.get_subnets_by_network(session, network_id)
        for subnet in subnets:
            cidr = subnet.get('cidr')
            condition = self.ipam.gm.get_infoblox_condition(network, subnet)
            network_view = condition.network_view
            ib_network = self.ipam.ibom.get_network(network_view, cidr)
            network_ea = eam.get_ea_for_network(user_id, tenant_id, network,
                                                subnet)
            self.ipam.ibom.update_network_options(ib_network, network_ea)

    def delete_network(self, network_id):
        pass

    def delete_network_sync(self, network_id):
        """Deletes infoblox entities that are associated with neutron network.

        db_base_plugin_v2 delete_network calls delete_subnet per subnet under
        the network so subnet deletion is not concerned here.
        """
        session = self.ipam.context.session
        ib_dbi.delete_management_ip(session, network_id)
        ib_dbi.remove_member_for_service(session, network_id=network_id)
        ib_dbi.dissociate_network_view(session, network_id)

    def create_subnet(self):
        pass

    def create_subnet_sync(self):
        session = self.ipam.context.session
        user_id = self.ipam.user_id
        network = self.ipam.network
        subnet = self.ipam.subnet
        tenant_id = subnet.get('tenant_id')
        network_id = subnet.get('network_id')
        #subnet_id = subnet.get('id')
        cidr = subnet.get('cidr')
        ip_version = subnet.get('ip_version')
        allocation_pools = subnet.get('allocation_pools')
        gateway_ip = subnet.get('gateway_ip')
        dns_nameservers = subnet.get('dns_nameservers', [])
        network_view = self.ipam.condition.network_view

        # 1. get network member
        # network member is the delegation member that owns this subnet in
        # NIOS.
        #network_member = reserved_members['network'][0]
        #if network_member.member_type == ib_const.MEMBER_TYPE_GRID_MASTER:
        #    delegate_member = None
        #else:
        #    delegate_member = network_member

        # 2. get dhcp members
        dhcp_members = self.ipam.condition.dhcp_members

        # 3. get dns members
        # for flat network we save member IP as a primary DNS server: to
        # the beginning of the list.
        # If this net is not flat, Member IP will later be replaced by
        # DNS relay IP.
        dns_grid_primary_members = self.ipam.condition.dns_members['primary']
        nameservers = [m.member_ip if ip_version == 4
                       else m.member_ipv6 for m in dns_grid_primary_members]
        nameservers += [n for n in dns_nameservers if n not in nameservers]

        # 4. get EAs
        network_view_ea = eam.get_ea_for_network_view(tenant_id)
        network_ea = eam.get_ea_for_network(user_id, tenant_id, network,
                                            subnet)
        range_ea = eam.get_ea_for_range(user_id, tenant_id, network)

        # 5. create network view and associate it to neutron network
        # any network whether it is external, shared, or private,
        # it can be predefined in NIOS and configured in
        # infoblox_conditional. in this case we will just update EAs.
        if self.ipam.ibom.network_exists(network_view, cidr):
            ib_network = self.ipam.ibom.get_network(network_view, cidr)
            self.ipam.ibom.update_network_options(ib_network, network_ea)
        else:
            # create a new network view
            self.ipam.ibom.create_network_view(network_view, network_view_ea)

        try:
            # 6. associate ib network view with neutron network
            # if network view is predefined, it needs to be associated with
            # neutron network here.
            ib_dbi.associate_network_view(session, network_view,
                                          network_id)

            # 7. create ib network which is equivalent to neutron subnet.
            network_template = self.ipam.condition.network_template
            if network_template:
                self.ipam.ibom.create_network_from_template(network_view,
                                                            cidr,
                                                            network_template)
            else:
                relay_trel_ip = ib_dbi.get_management_ip(session, network_id)
                self.ipam.ibom.create_network(network_view,
                                              cidr,
                                              nameservers=nameservers,
                                              dhcp_members=dhcp_members,
                                              gateway_ip=gateway_ip,
                                              relay_trel_ip=relay_trel_ip,
                                              extattrs=network_ea)

                for member in dhcp_members:
                    self.ipam.ibom.restart_all_services(member)

            # 8. create ip range under ib network
            for ip_range in allocation_pools:
                start_ip = ip_range['start']
                end_ip = ip_range['end']
                disable = True
                self.ipam.ibom.create_ip_range(network_view,
                                               start_ip,
                                               end_ip,
                                               cidr,
                                               disable,
                                               range_ea)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.debug("An exception occurred during subnet creation.")

                # revert the subnet creation
                #payload = {'payload': {'subnet_id': subnet_id}}
                #self.delete_subnet(payload)

    def update_subnet(self):
        pass

    def update_subnet_sync(self):
        session = self.ipam.context.session
        user_id = self.ipam.user_id
        network = self.ipam.network
        subnet = self.ipam.subnet
        tenant_id = subnet.get('tenant_id')
        network_id = subnet.get('network_id')
        subnet_id = subnet.get('id')
        cidr = subnet.get('cidr')
        dns_nameservers = subnet.get('dns_nameservers', [])
        network_view = self.ipam.condition.network_view

        ib_network = self.ipam.ibom.get_network(network_view, cidr)

        updated_nameservers = dns_nameservers
        if ib_network.member_ips and \
                ib_network.member_ips[0] in ib_network.dns_nameservers:
            # flat network, primary dns is member_ip
            primary_dns = ib_network.member_ips[0]
            updated_nameservers = [primary_dns] + dns_nameservers
        else:
            # network with relays, primary dns is relay_ip
            primary_dns = ib_dbi.get_subnet_dhcp_port_address(session,
                                                              subnet_id)
            if primary_dns:
                updated_nameservers = [primary_dns] + dns_nameservers

        ib_network.dns_nameservers = updated_nameservers

        network_ea = eam.get_ea_for_network(user_id, tenant_id, network,
                                            subnet)
        self.ipam.ibom.update_network_options(ib_network, network_ea)

        db_members = ib_dbi.get_members_in_service(session, network_id)
        members = ib_utils.db_records_to_obj('Member', db_members)
        for member in members:
            self.ipam.ibom.restart_all_services(member)

        return subnet

    def delete_subnet(self, subnet_id):
        pass

    def delete_subnet_sync(self, subnet_id):
        #session = self.ipam.context.session
        #user_id = self.ipam.user_id
        #network = self.ipam.network
        #subnet = self.ipam.subnet
        #tenant_id = subnet.get('tenant_id')
        #network_id = subnet.get('network_id')
        #subnet_id = subnet.get('id')
        pass

    def allocate_ip(self, ip_address, port_id, device_owner, device_id):
        pass

    def allocate_ip_sync(self, ip_address, mac, port_id, device_id,
                         device_owner):
        #session = self.ipam.context.session
        user_id = self.ipam.user_id
        network = self.ipam.network
        subnet = self.ipam.subnet
        tenant_id = subnet.get('tenant_id')
        #network_id = subnet.get('network_id')
        #subnet_id = subnet.get('id')
        network_view = self.ipam.condition.network_view
        dns_view = self.ipam.condition.dns_view

        hostname = uuidutils.generate_uuid()
        ip_ea = eam.get_ea_for_ip(user_id, tenant_id, network, port_id,
                                  device_id, device_owner)
        zone_auth = self.ipam.condition.pattern_builder.build_zone_name(
            network, subnet)
        allocated_ip = self.ipam.ip_allocator.allocate_given_ip(
            network_view, dns_view, zone_auth, hostname, mac, ip_address,
            ip_ea)
        if allocated_ip:
            return allocated_ip

        #for member in set(cfg.dhcp_members):
        #    self.infoblox.restart_all_services(member)

    def deallocate_ip(self, port):
        pass

    def deallocate_ip_sync(self, port_id):
        pass

    def create_floatingip_sync(self, port):
        pass

    def update_floatingip_sync(self, port_id):
        pass

    def delete_floatingip_sync(self, port_id):
        pass
