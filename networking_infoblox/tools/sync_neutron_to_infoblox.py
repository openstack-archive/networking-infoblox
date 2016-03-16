#!/usr/bin/env python
# Copyright 2015 Infoblox Inc.
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

import os
import sys

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import config as common_config

from neutron import context as neutron_context
from neutron.i18n import _LE
from neutron.i18n import _LW

from neutronclient.v2_0 import client as neutron_client
from novaclient import client as nova_client

from infoblox_client import exceptions as ib_exc

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context as ib_context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)

NOVA_API_VERSION = '2'
DEFAULT_CONFIG_FILES = ['/etc/neutron/neutron.conf']


def main():
    cfg.CONF(args=sys.argv[1:],
             default_config_files=DEFAULT_CONFIG_FILES)
    common_config.setup_logging()
    config.register_infoblox_ipam_opts(cfg.CONF)
    grid_id = cfg.CONF.infoblox.cloud_data_center_id
    config.register_infoblox_grid_opts(cfg.CONF, grid_id)

    credentials = get_credentials()
    if not credentials:
        print("\nYou must provide an admin user credentials in the shell "
              "environment.\nPlease export variables such as env[OS_USERNAME],"
              " env[OS_PASSWORD], env[OS_AUTH_URL], env[OS_TENANT_NAME], and "
              "env[OS_REGION_NAME]\n")
        return

    context = neutron_context.get_admin_context()

    grid_manager = grid.GridManager(context)
    grid_manager.sync(force_sync=True)

    sync_neutron_to_infoblox(context, credentials, grid_manager)


def get_credentials():
    d = dict()
    if ('OS_USERNAME' in os.environ and
            'OS_PASSWORD' in os.environ and
            'OS_AUTH_URL' in os.environ and
            'OS_TENANT_NAME' in os.environ and
            'OS_REGION_NAME' in os.environ):
        d['username'] = os.environ['OS_USERNAME']
        d['password'] = os.environ['OS_PASSWORD']
        d['auth_url'] = os.environ['OS_AUTH_URL']
        d['tenant_name'] = os.environ['OS_TENANT_NAME']
        d['region_name'] = os.environ['OS_REGION_NAME']
    return d


def sync_neutron_to_infoblox(context, credentials, grid_manager):
    """Sync neutron objects to Infoblox grid

    Prerequisites:
        1. network views to sync must have "Cloud Adapter ID" EA set.
        2. infoblox agent sync should have been processed and updated members
           and network views.
    """
    LOG.info("Starting migration...\n")

    grid_config = grid_manager.grid_config
    grid_id = grid_config.grid_id
    session = context.session

    neutron_api = neutron_client.Client(**credentials)
    payload = neutron_api.list_networks()
    networks = payload['networks']
    if not networks:
        LOG.info("No network exists...Exiting...")
        return

    payload = neutron_api.list_subnets()
    subnets = payload['subnets']
    if not subnets:
        LOG.info("No subnet exists...Exiting...")
        return

    payload = neutron_api.list_ports()
    ports = payload['ports']

    nova_api = nova_client.Client(NOVA_API_VERSION,
                                  credentials['username'],
                                  credentials['password'],
                                  credentials['tenant_name'],
                                  credentials['auth_url'])
    instances = dict()
    for server in nova_api.servers.list(search_opts={'all_tenants': 1}):
        instances[server.id] = server.name

    user_id = context.user_id or neutron_api.httpclient.auth_ref['user']['id']
    user_tenant_id = context.tenant_id or neutron_api.httpclient.auth_tenant_id

    should_exit = False
    for subnet in subnets:
        subnet_id = subnet['id']
        subnet_name = subnet['name']
        network_id = subnet['network_id']
        network = utils.find_one_in_list('id', network_id, networks)
        if not network:
            LOG.warning("network (%s) is not found. Skipping subnet (%s)",
                        network_id, subnet_id)
            continue

        network_name = network['name']
        db_mapped_netview = dbi.get_network_view_by_mapping(
            session,
            grid_id=grid_id,
            network_id=network_id,
            subnet_id=subnet_id)
        if db_mapped_netview:
            LOG.info("Mapping found for network (%s), subnet (%s)",
                     network_name, subnet_name)
            continue

        ib_cxt = ib_context.InfobloxContext(context, user_id,
                                            network, subnet,
                                            grid_config,
                                            plugin=neutron_api)
        ipam_controller = ipam.IpamSyncController(ib_cxt)
        dns_controller = dns.DnsController(ib_cxt)

        rollback_list = []
        try:
            ib_network = ipam_controller.create_subnet(rollback_list)
            if ib_network:
                dns_controller.create_dns_zones(rollback_list)
            LOG.info("Created network (%s), subnet (%s)",
                     network_name, subnet_name)
        except Exception as e:
            LOG.error(_LE("Error occurred: %(error)s"), {'error': e})
            for ib_obj in reversed(rollback_list):
                try:
                    ib_obj.delete()
                except ib_exc.InfobloxException as e:
                    LOG.warning(_LW("Unable to delete %(obj)s due to "
                                    "error: %(error)s."),
                                {'obj': ib_obj, 'error': e})
            should_exit = True
            break

    if should_exit:
        LOG.info("Exiting due to the error in creating subnet...")
        return

    for port in ports:
        port_id = port['id']
        port_mac_address = port['mac_address']
        tenant_id = port.get('tenant_id') or user_tenant_id
        network_id = port['network_id']
        device_owner = port['device_owner']
        device_id = port['device_id']

        instance_name = None
        if device_owner == const.NEUTRON_DEVICE_OWNER_COMPUTE_NOVA:
            instance_name = instances[device_id]

        network = utils.find_one_in_list('id', network_id, networks)
        if not network:
            LOG.error("network (%s) not found", network_id)
            break

        for ip_set in port.get('fixed_ips'):
            subnet_id = ip_set['subnet_id']
            ip_address = ip_set['ip_address']
            LOG.info("Adding port for %s: %s...", device_owner, ip_address)

            subnet = utils.find_one_in_list('id', subnet_id, subnets)
            if not subnet:
                should_exit = True
                LOG.error("subnet (%s) not found", subnet_id)
                break

            ib_cxt = ib_context.InfobloxContext(context, user_id,
                                                network, subnet,
                                                grid_config,
                                                plugin=neutron_api)
            connector = ib_cxt.connector
            netview = ib_cxt.mapping.network_view

            search_fields = {
                'network_view': netview,
                'ip_address': ip_address
            }
            obj_type = ('ipv4address'if utils.get_ip_version(ip_address) == 4
                        else 'ipv6address')
            ib_address = connector.get_object(obj_type,
                                              search_fields,
                                              return_fields=['objects'])
            if ib_address:
                LOG.info("%s is found...no need to create", ip_address)
                continue

            ipam_controller = ipam.IpamSyncController(ib_cxt)
            dns_controller = dns.DnsController(ib_cxt)

            allocated_ip = ipam_controller.allocate_specific_ip(
                ip_address,
                port_mac_address,
                port_id,
                tenant_id,
                device_id,
                device_owner)
            if allocated_ip and device_owner:
                try:
                    dns_controller.bind_names(
                        allocated_ip,
                        instance_name,
                        port_id,
                        tenant_id,
                        device_id,
                        device_owner)
                except Exception as e:
                    should_exit = True
                    LOG.error("Unable to allocate ip (%s): %s", ip_address, e)
                    ipam_controller.deallocate_ip(allocated_ip)
                    break

            LOG.info("Allocated %s", ip_address)

        if should_exit:
            LOG.info("Existing due to error in port creation...")
            break

    LOG.info("Ending migration...")


if __name__ == "__main__":
    main()
