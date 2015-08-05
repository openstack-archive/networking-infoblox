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
import oslo_messaging


LOG = logging.getLogger(__name__)


class IpamPreEventEndpoint(object):
    """Subscribes notification messages triggered by pre-committed IPAM
    actions and dispatches corresponding message handlers.

    The messages with the following event types are subscribed:
    - network.update.start
    - subnet.update.start
    """
    filter_rule = oslo_messaging.NotificationFilter(
        publisher_id='^network.*',
        event_type='^(network|subnet)\.update\.start$')

    def __init__(self, ipam_controller):
        self.ipam_controller = ipam_controller

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        resource, action, seq = event_type.split('.', 2)
        proc = EventProcessor(self.ipam_controller,
                              ctxt,
                              publisher_id,
                              event_type)
        method_name = "%s_%s_precommit" % (action, resource)
        method = getattr(proc, method_name)
        #result = method(payload)
        method(payload)


class IpamPostEventEndpoint(object):
    """Subscribes notification messages triggered by post-committed IPAM
    actions and dispatches corresponding message handlers.

    The subscribed messages have the following event types:
    - network.create.end
    - network.update.end
    - network.delete.end
    - subnet.create.end
    - subnet.update.end
    - subnet.delete.end
    - port.create.end
    - port.update.end
    - port.delete.end
    - floatingip.create.end
    - floatingip.update.end
    - floatingip.delete.end
    """
    filter_rule = oslo_messaging.NotificationFilter(
        publisher_id='^network.*',
        event_type='^(network|subnet|port|floatingip)\..*\.end$')

    def __init__(self, ipam_controller):
        self.ipam_controller = ipam_controller

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        resource, action, seq = event_type.split('.', 2)
        proc = EventProcessor(self.ipam_controller,
                              ctxt,
                              publisher_id,
                              event_type)
        method_name = "%s_%s_postcommit" % (action, resource)
        method = getattr(proc, method_name)
        #result = method(payload)
        method(payload)


class InstanceEventEndpoint(object):
    """Subscribes instance creation message from nova which contains
    instance's hostname.

    The subscribing event type:
    - compute.instance.create.end
    """
    filter_rule = oslo_messaging.NotificationFilter(
        publisher_id='^compute.*',
        event_type='^compute\.instance\.create\.end$')

    def __init__(self, ipam_controller):
        self.ipam_controller = ipam_controller

    def info(self, ctxt, publisher_id, event_type, payload, metadata):
        proc = EventProcessor(self.ipam_controller,
                              ctxt,
                              publisher_id,
                              event_type)
        method_name = 'create_instance_postcommit'
        method = getattr(proc, method_name)
        #result = method(payload)
        method(payload)


class EventProcessor(object):
    """IPAM event processor syncs pre-committed IPAM actions with IPAM driver
    and propagates IPAM actions committed in neutron to the external backend.
    """
    TRACEABLE = True

    def __init__(self, ipam_controller, ctxt, publisher_id, event_type):
        self.ipam_controller = ipam_controller
        self._get_context(ctxt, publisher_id)

    def _get_context(self, ctxt, publisher_id):
        """Get common information from the message context"""
        self.publisher_id = publisher_id
        self.message_context = ctxt

        # user info
        self.is_admin = ctxt.get('is_admin')
        self.user_id = ctxt.get('user_id')
        self.user_name = ctxt.get('user_name')
        self.roles = ctxt.get('roles')

        # tenant info
        self.tenant_id = ctxt.get('tenant_id')
        self.tenant_name = ctxt.get('tenant_name')

        self.timestamp = ctxt.get('timestamp')

    def create_instance_postcommit(self, payload):
        """Handle instance creation event.
        """
        instance_id = payload.get('instance_id')
        host = payload.get('host')

        if self.TRACEABLE:
            LOG.debug("instance_id: %s, host: %s" % (instance_id, host))

    def create_network_postcommit(self, payload):
        """Handle creation of network(s) in the external backend."""
        if 'networks' in payload:
            networks = payload.get('networks')
        else:
            networks = [payload.get('network')]

        if self.TRACEABLE:
            LOG.debug("networks: %s" % networks)

        for network in networks:
            #id = network.get('id')
            #name = network.get('name')
            #tenant_id = network.get('tenant_id')
            #admin_state_up = network.get('admin_state_up')
            #status = network.get('status')
            #external = network.get('router:external', False)
            #shared = network.get('shared')
            #subnets = network.get('subnets')
            #provider_network_type =
            #network.get('provider:network_type')
            #provider_physical_network =
            #   network.get('provider:physical_network')
            #provider_segmentation_id =
            #   network.get('provider:segmentation_id')
            self.ipam_controller.create_network_sync(self.message_context,
                                                     network)

    def update_network_postcommit(self, payload):
        """Handle a network update in the external backend."""
        network = payload.get('network')

        if self.TRACEABLE:
            LOG.debug("network: %s" % network)

        # id = network.get('id')
        # name = network.get('name')
        # tenant_id = network.get('tenant_id')
        # admin_state_up = network.get('admin_state_up')
        # status = network.get('status')
        # external = network.get('router:external', False)
        # shared = network.get('shared')
        # subnets = network.get('subnets')
        # provider_network_type = network.get('provider:network_type')
        # provider_physical_network = network.get('provider:physical_network')
        # provider_segmentation_id = network.get('provider:physical_network')
        self.ipam_controller.update_network_sync(self.message_context,
                                                 network)

    def delete_network_postcommit(self, payload):
        """Handle a network deletion in the external backend."""
        network_id = payload.get('network_id')

        if self.TRACEABLE:
            LOG.debug("network_id: %s" % network_id)

        # At this point, NIOS subnets that belong to the networks
        # should have been removed.
        # Check if still exists and remove them if necessary.
        self.ipam_controller.delete_network_sync(self.message_context,
                                                 network_id)

    def create_subnet_postcommit(self, payload):
        """Handle creation of subnet(s) in the external backend."""
        if 'subnets' in payload:
            subnets = payload.get('subnets')
        else:
            subnets = [payload.get('subnet')]

        if self.TRACEABLE:
            LOG.debug("subnets: %s" % subnets)

        for subnet in subnets:
            # id = subnet.get('id')
            # name = subnet.get('name')
            # subnetpool_id = subnet.get('subnetpool_id')
            # enable_dhcp = subnet.get('enable_dhcp')
            # network_id = subnet.get('network_id')
            # tenant_id = subnet.get('tenant_id')
            # dns_nameservers = subnet.get('dns_nameservers')
            # ipv6_ra_mode = subnet.get('ipv6_ra_mode')
            # allocation_pools = subnet.get('allocation_pools')
            # gateway_ip = subnet.get('gateway_ip')
            # ipv6_address_mode = subnet.get('ipv6_address_mode')
            # ip_version = subnet.get('ip_version')
            # host_routes = subnet.get('host_routes')
            # cidr = subnet.get('cidr')
            # subnetpool_id = subnet.get('subnetpool_id')

            self.ipam_controller.create_subnet_sync(self.message_context,
                                                    subnet)

    def update_subnet_postcommit(self, payload):
        """Handle a subnet update in the external backend."""
        subnet = payload.get('subnet')

        if self.TRACEABLE:
            LOG.debug("subnet: %s" % subnet)

        # id = subnet.get('id')
        # name = subnet.get('name')
        # subnetpool_id = subnet.get('subnetpool_id')
        # enable_dhcp = subnet.get('enable_dhcp')
        # network_id = subnet.get('network_id')
        # tenant_id = subnet.get('tenant_id')
        # dns_nameservers = subnet.get('dns_nameservers')
        # ipv6_ra_mode = subnet.get('ipv6_ra_mode')
        # allocation_pools = subnet.get('allocation_pools')
        # gateway_ip = subnet.get('gateway_ip')
        # ipv6_address_mode = subnet.get('ipv6_address_mode')
        # ip_version = subnet.get('ip_version')
        # host_routes = subnet.get('host_routes')
        # cidr = subnet.get('cidr')
        # subnetpool_id = subnet.get('subnetpool_id')

        self.ipam_controller.update_subnet_sync(self.message_context, subnet)

    def delete_subnet_postcommit(self, payload):
        """Handle a subnet deletion in the external backend."""
        subnet_id = payload.get('subnet_id')

        if self.TRACEABLE:
            LOG.debug("subnet_id: %s" % subnet_id)

        # At this point, NIOS subnets should have been removed.
        # Check if still exists and remove them if necessary.
        self.ipam_controller.delete_subnet_sync(self.message_context,
                                                subnet_id)

    def create_port_postcommit(self, payload):
        """Handle creation of port(s) in the external backend."""
        if 'ports' in payload:
            ports = payload.get('ports')
        else:
            ports = [payload.get('port')]

        if self.TRACEABLE:
            LOG.debug("ports: %s" % ports)

        #for port in ports:
        #     id = port.get('id')
        #     name = port.get('name')
        #     status = port.get('status')
        #     allowed_address_pairs = port.get('allowed_address_pairs')
        #     admin_state_up = port.get('admin_state_up')
        #     network_id = port.get('network_id')
        #     tenant_id = port.get('tenant_id')
        #     extra_dhcp_opts = port.get('extra_dhcp_opts')
        #     binding_host_id = port.get('binding:host_id')
        #     binding_vnic_type = port.get('binding:vnic_type')
        #     binding_vif_type = port.get('binding:vif_type')
        #     binding_vif_details = port.get('binding:vif_details')
        #     binding_profile = port.get('binding:profile')
        #     device_owner = port.get('device_owner')
        #     mac_address = port.get('mac_address')
        #     fixed_ips = port.get('fixed_ips')
        #     security_groups = port.get('security_groups')
        #     device_id = port.get('device_id')
        self.ipam_controller.create_port_sync(self.message_context, ports)

    def update_port_postcommit(self, payload):
        """Handle a port update in the external backend."""
        port = payload.get('port')

        if self.TRACEABLE:
            LOG.debug("port: %s" % port)

        # id = port.get('id')
        # name = port.get('name')
        # status = port.get('status')
        # allowed_address_pairs = port.get('allowed_address_pairs')
        # admin_state_up = port.get('admin_state_up')
        # network_id = port.get('network_id')
        # tenant_id = port.get('tenant_id')
        # extra_dhcp_opts = port.get('extra_dhcp_opts')
        # binding_host_id = port.get('binding:host_id')
        # binding_vnic_type = port.get('binding:vnic_type')
        # binding_vif_type = port.get('binding:vif_type')
        # binding_vif_details = port.get('binding:vif_details')
        # binding_profile = port.get('binding:profile')
        # device_owner = port.get('device_owner')
        # mac_address = port.get('mac_address')
        # fixed_ips = port.get('fixed_ips')
        # security_groups = port.get('security_groups')
        # device_id = port.get('device_id')

    def delete_port_postcommit(self, payload):
        """Handle a port deletion in the external backend."""
        port_id = payload.get('port_id')

        if self.TRACEABLE:
            LOG.debug("port_id: %s" % port_id)

    def create_floatingip_postcommit(self, payload):
        """Handle a floating ip creation in the external backend.

        There are two types of responses with this event:
        1. floating ip creation
            'floatingip': {
              'router_id': None,
              'status': 'DOWN',
              'tenant_id': '83718697a30c4901b955f21991a40ab9',
              'floating_network_id': '7a382144-b6ab-4329-8d31-58dc34fa7f16',
              'fixed_ip_address': None,
              'floating_ip_address': '172.24.4.126',
              'port_id': None,
              'id': '4f30c951-c7db-4e7d-a53d-ed2ca0638e5d'
            }
        2. floating ip association
            'floatingip': {
              'router_id': 'f7e0e68d-aaab-41a7-8275-ff01f4859810',
              'status': 'DOWN',
              'tenant_id': 'bd9338315ecb462ba285e055f4dcc6b2',
              'floating_network_id': '7a382144-b6ab-4329-8d31-58dc34fa7f16',
              'fixed_ip_address': '10.100.0.13',
              'floating_ip_address': '172.24.4.135',
              'port_id': '59c385c1-61cc-46c6-bec4-9d1d38ab68f0',
              'id': '5eb54b78-1c1e-466b-8866-5e118f6412b0'
            }
        """
        floatingip = payload.get('floatingip')

        if self.TRACEABLE:
            LOG.debug("floatingip: %s" % floatingip)

        # id = floatingip.get('id')
        # router_id = floatingip.get('router_id')
        # status = floatingip.get('status')
        # tenant_id = floatingip.get('tenant_id')
        # floating_network_id = floatingip.get('floating_network_id')
        # fixed_ip_address = floatingip.get('fixed_ip_address')
        # floating_ip_address = floatingip.get('floating_ip_address')
        port_id = floatingip.get('port_id')

        if port_id is None:
            # call floating ip creation
            pass
        else:
            # call floating ip association
            pass

    def update_floatingip_postcommit(self, payload):
        """Handle a floating ip update in the external backend.

        update could be either association if port_id is not empty or
        dissociation if port_id is None.
        """
        floatingip = payload.get('floatingip')

        if self.TRACEABLE:
            LOG.debug("floatingip: %s" % floatingip)

        # id = floatingip.get('id')
        # router_id = floatingip.get('router_id')
        # status = floatingip.get('status')
        # tenant_id = floatingip.get('tenant_id')
        # floating_network_id = floatingip.get('floating_network_id')
        # fixed_ip_address = floatingip.get('fixed_ip_address')
        # floating_ip_address = floatingip.get('floating_ip_address')
        # port_id = floatingip.get('port_id')

    def delete_floatingip_postcommit(self, payload):
        """Handle a floating ip deletion in the external backend."""
        floatingip_id = payload.get('floatingip_id')

        if self.TRACEABLE:
            LOG.debug("floatingip_id: %s" % floatingip_id)
