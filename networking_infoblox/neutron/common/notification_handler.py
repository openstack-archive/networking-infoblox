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

import netaddr
from oslo_log import log as logging
import oslo_messaging
from oslo_utils import encodeutils
from sqlalchemy import exc as sql_exc

from infoblox_client import objects as ib_objects

from neutron import manager

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import keystone_manager
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class IpamEventHandler(object):

    traceable = True

    def __init__(self, neutron_context, plugin=None, grid_manager=None):
        self.context = neutron_context
        self.plugin = plugin if plugin else manager.NeutronManager.get_plugin()
        if grid_manager:
            self.grid_mgr = grid_manager
        else:
            self.grid_mgr = grid.GridManager(self.context)
            self.grid_mgr.sync(True)

        self.grid_config = self.grid_mgr.grid_config
        self.grid_id = self.grid_config.grid_id

        self._cached_grid_members = None
        self._cached_network_views = None
        self._cached_mapping_conditions = None

    def _resync(self, force_sync=False):
        self.grid_mgr.sync(force_sync)

        self._cached_grid_members = dbi.get_members(
            self.context.session, grid_id=self.grid_id,
            member_status=const.MEMBER_STATUS_ON)
        self._cached_network_views = dbi.get_network_views(
            self.context.session, grid_id=self.grid_id)
        self._cached_mapping_conditions = dbi.get_mapping_conditions(
            self.context.session, grid_id=self.grid_id)

    def process(self, ctxt, publisher_id, event_type, payload, metadata):
        self.ctxt = ctxt
        self.user_id = self.ctxt.get('user_id')

        try:
            handler_name = utils.get_notification_handler_name(event_type)
            handler = getattr(self, handler_name)
            if handler:
                handler(payload)
            return oslo_messaging.NotificationResult.HANDLED
        except sql_exc.OperationalError as e:
            LOG.info("Operational Error occurred. Please restart the agent.")
            LOG.error(encodeutils.exception_to_unicode(e))
        except Exception as e:
            LOG.error(encodeutils.exception_to_unicode(e))

    def create_network_alert(self, payload):
        """Notifies that new networks are about to be created.

        Upon alert, trigger grid sync and record tenant names
        """
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        if self.traceable:
            for network in networks:
                LOG.info("Creating network: %s", network)

        self._resync()

    def create_subnet_alert(self, payload):
        """Notifies that new subnets are about to be created.

        Upon alert, trigger grid sync and record tenant names
        """
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        if self.traceable:
            for subnet in subnets:
                LOG.info("Creating subnet: %s", subnet)

        self._resync()

    def create_network_sync(self, payload):
        """Notifies that new networks have been created."""
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        for network in networks:
            if self.traceable:
                LOG.info("Created network: %s", network)
            dbi.add_or_update_network(self.context.session,
                                      network.get('id'), network.get('name'))

        if self.grid_config.tenant_name_persistence:
            keystone_manager.update_tenant_mapping(self.context,
                                                   networks,
                                                   self.ctxt['tenant_id'],
                                                   self.ctxt['tenant_name'],
                                                   self.ctxt['auth_token'])

    def update_network_sync(self, payload):
        """Notifies that the network property has been updated."""
        network = payload.get('network')

        if self.traceable:
            LOG.info("Updated network: %s", network)

        ib_context = context.InfobloxContext(self.context, self.user_id,
                                             network, None, self.grid_config,
                                             self.plugin)
        ipam_controller = ipam.IpamAsyncController(ib_context)
        network_id = network.get('id')
        new_name = network.get('name')
        old_network = dbi.get_network(self.context.session, network_id)
        need_new_zones = False
        if new_name is not None and (
                old_network is None or new_name != old_network.network_name):
            dbi.add_or_update_network(self.context.session,
                                      network_id, new_name)
            pattern = self.grid_config.default_domain_name_pattern
            if '{network_name}' in pattern:
                need_new_zones = True
        ipam_controller.update_network_sync(need_new_zones)

    def delete_network_sync(self, payload):
        """Notifies that the network has been deleted."""
        network_id = payload.get('network_id')

        if self.traceable:
            LOG.info("Deleted network: %s", network_id)

        self._resync()
        dbi.remove_network(self.context.session, network_id)

    def create_subnet_sync(self, payload):
        """Notifies that new subnets have been created."""
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        for subnet in subnets:
            if self.traceable:
                LOG.info("Created subnet: %s", subnet)

        self._resync(True)

    def update_subnet_sync(self, payload):
        """Notifies that the subnet has been updated."""
        subnet = payload.get('subnet')

        if self.traceable:
            LOG.info("Updated subnet: %s", subnet)

        self._resync(True)

    def delete_subnet_sync(self, payload):
        """Notifies that the subnet has been deleted."""
        subnet_id = payload.get('subnet_id')

        if self.traceable:
            LOG.info("Deleted subnet: %s", subnet_id)

        self._resync(True)

    def create_port_sync(self, payload):
        """Notifies that new ports have been created.

        When allocating an ip address from IPAM driver, port creation is not
        committed so port id is not yet available. So we update Port ID EA in
        this event.
        """
        if 'ports' in payload:
            ports = payload.get('ports')
        else:
            ports = [payload.get('port')]

        for port in ports:
            if self.traceable:
                LOG.info("Created port: %s", port)

    def _process_port(self, port, event, instance_name=None):
        for fixed_ip in port['fixed_ips']:
            subnet_id = fixed_ip['subnet_id']
            subnet = self.plugin.get_subnet(self.context, subnet_id)
            if not subnet:
                LOG.warning("No subnet was found for subnet_id=%s",
                            subnet_id)
                continue

            ib_context = context.InfobloxContext(
                self.context, self.user_id, None, subnet, self.grid_config,
                self.plugin, self._cached_grid_members,
                self._cached_network_views,
                self._cached_mapping_conditions)

            dns_controller = dns.DnsController(ib_context)

            if instance_name is not None:
                dns_controller.bind_names(fixed_ip['ip_address'],
                                          instance_name,
                                          port['id'],
                                          port['tenant_id'],
                                          port['device_id'],
                                          port['device_owner'],
                                          port_name=port['name'])
                LOG.info(
                    "%s sync: ip = %s, instance name = %s, "
                    "port id = %s, device id: %s, device owner: %s", event,
                    fixed_ip['ip_address'], instance_name, port['id'],
                    port['device_id'], port['device_owner'])
            else:
                dns_controller.unbind_names(
                    fixed_ip['ip_address'], None, port['id'],
                    port['tenant_id'], None,
                    const.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA,
                    port_name=port['name'])

    def update_port_sync(self, payload):
        """Notifies that the port has been updated."""
        port = payload.get('port')

        if 'binding:vif_type' in port:
            instance_name = None
            if port['device_owner'] in const.NEUTRON_DEVICE_OWNER_COMPUTE_LIST:
                instance = dbi.get_instance(self.context.session,
                                            port['device_id'])
                if instance:
                    instance_name = instance.instance_name
            event = 'Port update'
            if port['binding:vif_type'] == 'unbound':
                self._process_port(port, event, None)
            elif instance_name is not None:
                self._process_port(port, event, instance_name)

        if self.traceable:
            LOG.info("Updated port: %s", port)

    def delete_port_sync(self, payload):
        """Notifies that the port has been deleted."""
        port_id = payload.get('port_id')

        if self.traceable:
            LOG.info("Deleted port: %s", port_id)

    def create_floatingip_sync(self, payload):
        """Notifies that a new floating ip has been created.

        There are two types of responses with this event:
        1. floating ip creation: this response comes with no port_id and
        fixed_ip_address.

        2. floating ip association with fixed_ip_address: this response
        contains port_id and fixed_ip_address.
        """
        floatingip = payload.get('floatingip')

        if self.traceable:
            LOG.info("Created floatingip: %s", floatingip)

    def _get_instance_name_from_fip(self, floatingip):
        """Get instance name from fip associated with an instance

        Get instance name using the following info. in floatingip:
        1. port_id - this is the port id for the instance
        2. fixed_ip_address - this is the fixed ip for the instance

        Using the above, construct InfobloxContext and query NIOS
        for FixedAddress/HostRecord for instance. From the result,
        extract instance name from the "VM Name" EA
        """
        port_id = floatingip.get('port_id')
        fixed_ip = floatingip.get('fixed_ip_address')

        port = self.plugin.get_port(self.context, port_id)
        if not port:
            LOG.warning("No port found for port_id: %s" % port_id)
            return None

        if port['device_owner'] in const.NEUTRON_DEVICE_OWNER_COMPUTE_LIST:
            instance = dbi.get_instance(self.context.session,
                                        port['device_id'])
            if instance:
                return instance.instance_name

        subnet_ids = [ip['subnet_id'] for ip in port['fixed_ips']
                      if ip['ip_address'] == fixed_ip]
        if not subnet_ids:
            LOG.warning("No subnet_ids found for port: %s, fixed_ip: " %
                        (port, fixed_ip))
            return None

        subnet = self.plugin.get_subnet(self.context, subnet_ids[0])
        if not subnet:
            LOG.warning("No subnet was found for subnet_id: %s" %
                        subnet_ids[0])
            return

        ib_context = context.InfobloxContext(self.context, self.user_id,
                                             None, subnet, self.grid_config,
                                             self.plugin,
                                             self._cached_grid_members,
                                             self._cached_network_views,
                                             self._cached_mapping_conditions)

        connector = ib_context.connector
        netview = ib_context.mapping.network_view
        dns_view = ib_context.mapping.dns_view
        ib_address = ib_objects.FixedAddress.search(connector,
                                                    network_view=netview,
                                                    ip=fixed_ip)
        if not ib_address:
            ib_address = ib_objects.HostRecord.search(connector,
                                                      view=dns_view,
                                                      ip=fixed_ip)
            if not ib_address:
                return None

        return ib_address.extattrs.get(const.EA_VM_NAME)

    def update_floatingip_sync(self, payload):
        """Notifies that the floating ip has been updated.

        update could be either association if port_id is not empty or
        dissociation if port_id is None.
        """
        floatingip = payload.get('floatingip')

        if self.traceable:
            LOG.info("Updated floatingip: %s", floatingip)

        session = self.context.session
        floating_ip_id = floatingip.get('id')
        tenant_id = floatingip.get('tenant_id')
        associated_port_id = floatingip.get('port_id')
        network_id = floatingip.get('floating_network_id')
        floating_ip = floatingip.get('floating_ip_address')
        instance_name = None

        # find mapping subnet id by network id and floating ip since
        # subnet info is not passed.
        subnet = self._get_mapping_neutron_subnet(network_id, floating_ip)
        if subnet is None:
            return

        network = self.plugin.get_network(self.context, network_id)
        ib_context = context.InfobloxContext(self.context, self.user_id,
                                             network, subnet, self.grid_config,
                                             self.plugin,
                                             self._cached_grid_members,
                                             self._cached_network_views,
                                             self._cached_mapping_conditions)
        dns_controller = dns.DnsController(ib_context)

        if associated_port_id:
            instance_name = self._get_instance_name_from_fip(floatingip)
            is_floating_ip = True
            db_port = dbi.get_port_by_id(session, associated_port_id)
        else:
            is_floating_ip = False
            db_floatingip = dbi.get_floatingip_by_id(session, floating_ip_id)
            db_port = dbi.get_port_by_id(session,
                                         db_floatingip.floating_port_id)

        dns_controller.bind_names(floating_ip,
                                  instance_name,
                                  db_port.id,
                                  tenant_id,
                                  db_port.device_id,
                                  db_port.device_owner,
                                  is_floating_ip,
                                  db_port.name)
        LOG.info("Floating ip update sync: floating ip = %s, "
                 "instance name = %s, port id = %s, device id: %s, "
                 "device owner = %s",
                 floating_ip, instance_name, db_port.id, db_port.device_id,
                 db_port.device_owner)

    def _get_mapping_neutron_subnet(self, network_id, floating_ip):
        """Search subnet by network id and floating ip.

        Iterates through subnets from db and finds cidr that matches
        floaging ip.
        returns: subnet dict for floating ip and network id combination or
                 None if no subnet was found.
        """
        subnets = self.plugin.get_subnets_by_network(self.context, network_id)
        for subnet in subnets:
            if (netaddr.IPAddress(floating_ip) in
                    netaddr.IPNetwork(subnet['cidr'])):
                return subnet

    def delete_floatingip_sync(self, payload):
        """Notifies that the floating ip has been deleted."""
        floatingip_id = payload.get('floatingip_id')

        if self.traceable:
            LOG.info("Deleted floatingip: %s", floatingip_id)

    def create_instance_sync(self, payload):
        """Notifies that an instance has been created."""
        instance_id = payload.get('instance_id')
        instance_name = payload.get('hostname')
        dbi.add_or_update_instance(self.context.session,
                                   instance_id, instance_name)
        if self.traceable:
            LOG.info("Created instance: %s, host: %s",
                     instance_id, instance_name)

        ips = payload.get('fixed_ips')
        if not ips:
            return

        macs = [ip.get('vif_mac') for ip in ips if ip.get('vif_mac')]
        ip_addresses = [ip['address'] for ip in ips]
        port_filter = {'mac_address': macs,
                       'fixed_ips': {'ip_address': ip_addresses}}
        ports = self.plugin.get_ports(self.context, filters=port_filter)
        for port in ports:
            self._process_port(port, 'Instance creation', instance_name)

    def delete_instance_sync(self, payload):
        """Notifies that an instance has been deleted."""
        instance_id = payload.get('instance_id')
        session = self.context.session
        dbi.remove_instance(session, instance_id)
        if self.traceable:
            LOG.info("Deleted instance: %s", instance_id)

        vm_id_ea = ib_objects.EA({'VM ID': instance_id})
        subnets = dbi.get_external_subnets(self.context.session)
        for cur_subnet in subnets:
            subnet = self.plugin.get_subnet(self.context,
                                            cur_subnet.id)
            network = self.plugin.get_network(self.context,
                                              cur_subnet.network_id)
            ib_context = context.InfobloxContext(
                self.context, self.user_id, network, subnet,
                self.grid_config, self.plugin, self._cached_grid_members,
                self._cached_network_views, self._cached_mapping_conditions)
            dns_controller = dns.DnsController(ib_context)

            connector = ib_context.connector
            netview = ib_context.mapping.network_view
            dns_view = ib_context.mapping.dns_view
            ib_address = ib_objects.FixedAddress.search(
                connector, network_view=netview, network=subnet['cidr'],
                search_extattrs=vm_id_ea)

            if not ib_address:
                ib_address = ib_objects.HostRecord.search(
                    connector, view=dns_view, zone=dns_controller.dns_zone,
                    search_extattrs=vm_id_ea)

            if not ib_address:
                continue

            if hasattr(ib_address, 'ips'):
                ips = [ipaddr.ip for ipaddr in ib_address.ips
                       if netaddr.IPAddress(ipaddr.ip) in
                       netaddr.IPNetwork(subnet['cidr'])]
            else:
                ips = [ib_address.ip]

            tenant_id = ib_address.extattrs.get('Tenant ID')
            db_ports = dbi.get_floatingip_ports(
                session, ips, cur_subnet.network_id)
            for port in db_ports:
                port_id = port[0]
                device_id = port[1]
                device_owner = port[2]
                floating_ip = port[3]
                port_name = port[4]
                dns_controller.bind_names(
                    floating_ip, None, port_id, tenant_id,
                    device_id, device_owner, False, port_name)
                LOG.info("Instance deletion sync: instance id = %s, "
                         "floating ip = %s, port id = %s, device owner = %s",
                         instance_id, floating_ip, port_id, device_owner)
