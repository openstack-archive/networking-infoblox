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
#from oslo_serialization import jsonutils
#from oslo_utils import excutils

from neutron import context
#from neutron.ipam.drivers.infoblox.common import config as ib_conf
#from neutron.ipam.drivers.infoblox.common import connector
#from neutron.ipam.drivers.infoblox.common import constants as ib_const
from neutron.ipam.drivers.infoblox.common import dhcp
from neutron.ipam.drivers.infoblox.common import dns
#from neutron.ipam.drivers.infoblox.common import exceptions as ib_exc
from neutron.ipam.drivers.infoblox.common import grid
from neutron.ipam.drivers.infoblox.common import ibom
from neutron.ipam.drivers.infoblox.common import ip_allocator
from neutron.ipam.drivers.infoblox.common import utils as ib_utils
from neutron.ipam.drivers.infoblox.db import db_api as ib_dbi
from neutron import manager


LOG = logging.getLogger(__name__)


class IpamController(object):

    def __init__(self):
        self.context = context.get_admin_context()
        self.plugin = manager.NeutronManager.get_plugin()
        self.gm = grid.GridManager(self.context)
        self.gm.sync()

    def validate_network_change(self, request):
        pass

    def validate_subnet_change(self, request):
        pass

    def create_network_sync(self, message_context, network):
        user_id = message_context.get('user_id')
        #import pdb; pdb.set_trace()
        # FIXME: (HS)
        # need to find out what we should use: condition config or extension,
        # if condition config is used, we need to add more option to know
        # which condition will fall for this network since no subnet is
        # created yet.
        ipam_mgr = IpamManager(self.context, user_id, self.gm, network)
        dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        dhcp_driver.create_network_sync()

    def update_network_sync(self, message_context, network):
        user_id = message_context.get('user_id')
        #import pdb; pdb.set_trace()
        ipam_mgr = IpamManager(self.context, user_id, self.gm, network)
        dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        dhcp_driver.update_network_sync()

    def delete_network_sync(self, message_context, network_id):
        #import pdb; pdb.set_trace()
        user_id = message_context.get('user_id')
        ipam_mgr = IpamManager(self.context, user_id, self.gm)
        dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        dhcp_driver.delete_network_sync(network_id)

    def create_subnet_sync(self, message_context, subnet):
        user_id = message_context.get('user_id')
        network_id = subnet.get('network_id')

        #import pdb; pdb.set_trace()
        # get network from plugin so that physical network info is available.
        network = self.plugin.get_network(self.context, network_id)

        # reserve network and service members
        condition = self.gm.reserve_members_for_subnet(network, subnet)

        ipam_mgr = IpamManager(self.context, user_id, self.gm, network,
                               subnet, condition)

        dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        dhcp_driver.create_subnet_sync()

        dns_driver = dns.DnsDriver(ipam_mgr)
        dns_driver.create_dns_zones()

    def update_subnet_sync(self, message_context, subnet):
        user_id = message_context.get('user_id')
        network_id = subnet.get('network_id')

        #import pdb; pdb.set_trace()
        network = self.plugin.get_network(self.context, network_id)

        ipam_mgr = IpamManager(self.context, user_id, self.gm, network,
                               subnet)
        dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        dhcp_driver.update_subnet_sync()

    def delete_subnet_sync(self, message_context, subnet_id):
        #session = self.context.session
        #user_id = message_context.get('user_id')

        #import pdb; pdb.set_trace()
        #db_network = ib_dbi.get_network_by_subnet(session, subnet_id)
        #network = self.plugin.get_network(self.context, db_network['id'])

        #ipam_mgr = IpamManager(self.context, user_id, self.gm, network)
        #dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
        #dhcp_driver.delete_subnet_sync(subnet_id)
        pass

    def create_port_sync(self, message_context, port):
        session = self.context.session
        user_id = message_context.get('user_id')
        network_id = port.get('network_id')
        port_id = port.get('id')
        device_id = port.get('device_id')
        device_owner = port.get('device_owner')
        fixed_ips = port.get('fixed_ips')
        mac_address = port.get('mac_address')

        #import pdb; pdb.set_trace()
        for fixed_ip in fixed_ips:
            subnet_id = fixed_ip.get('subnet_id')
            ip_address = fixed_ip.get('ip_address')
            if subnet_id is None:
                break

            db_network = ib_dbi.get_network(session, network_id)
            networks = ib_utils.db_records_to_obj('Network', db_network)
            db_subnet = ib_dbi.get_subnet(session, subnet_id)
            subnets = ib_utils.db_records_to_obj('Subnet', db_subnet)
            ipam_mgr = IpamManager(self.context, user_id, self.gm, networks[0],
                                   subnets[0])
            dhcp_driver = dhcp.DhcpDriver(ipam_mgr)
            dhcp_driver.allocate_ip_sync(ip_address, mac_address, port_id,
                                         device_id, device_owner)

    def update_port_sync(self, payload):
        pass

    def delete_port_sync(self, payload):
        pass

    def create_floatingip_sync(self, payload):
        pass

    def update_floatingip_sync(self, payload):
        pass

    def delete_floatingip_sync(self, payload):
        pass


class IpamManager(object):

    def __init__(self, neutron_context, user_id, grid_manager, network=None,
                 subnet=None, condition=None):
        self.context = neutron_context
        self.user_id = user_id
        self.gm = grid_manager
        self.network = network
        self.subnet = subnet
        self.condition = condition

        if network is None:
            self.condition = None
            self.ibom = None
            self.ip_allocator = None
        else:
            if not self.condition:
                self.condition = self.gm.get_infoblox_condition(self.network,
                                                                self.subnet)
            self.ibom = ibom.InfobloxObjectManager(self.condition)
            self.ip_allocator = ip_allocator.IPAllocatorFactory(self.ibom)
