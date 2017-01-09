#!/usr/bin/env python
# Copyright 2016 Infoblox Inc.
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

from keystoneauth1.identity import v2
from keystoneauth1.identity import v3
from keystoneauth1 import session as ks_session
from keystoneclient.v2_0 import client as client_2_0
from keystoneclient.v3 import client as client_3

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import config as common_config
from neutron import context as neutron_context

from neutronclient.v2_0 import client as neutron_client
from novaclient import client as nova_client

from infoblox_client import exceptions as ib_exc
from infoblox_client import objects as ib_objects

from networking_infoblox._i18n import _LE
from networking_infoblox._i18n import _LW
from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import context as ib_context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import grid
from networking_infoblox.neutron.common import ipam
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.BoolOpt('delete-unknown-ips',
                short='dui',
                default=False,
                help=('Delete IP from Infoblox that are '
                      'unknown to OpenStack. '
                      'NOTE: only unknown IP in private network '
                      'will be deleted by this tool. '
                      'Unknown IP in shared/external network need '
                      'to be deleted manually.'))
]

cfg.CONF.register_cli_opts(cli_opts)

NOVA_API_VERSION = '2'
DEFAULT_CONFIG_FILES = ['/etc/neutron/neutron.conf']


def main():
    cfg.CONF(args=sys.argv[1:],
             default_config_files=DEFAULT_CONFIG_FILES)
    common_config.setup_logging()
    config.register_infoblox_ipam_opts(cfg.CONF)
    grid_id = cfg.CONF.infoblox.cloud_data_center_id
    config.register_infoblox_grid_opts(cfg.CONF, grid_id)
    register_keystone_opts(cfg.CONF)

    try:
        credentials, version = get_credentials()
    except KeyError:
        print("\nYou must provide an admin user credentials in the shell "
              "environment.\nPlease export variables such as env[OS_USERNAME],"
              " env[OS_PASSWORD], env[OS_AUTH_URL], env[OS_TENANT_NAME], and "
              "env[OS_REGION_NAME]\n")
        return

    password_creds = credentials.copy()
    password_creds.pop('region_name', None)
    if version == '3':
        auth = v3.Password(**password_creds)
        session = ks_session.Session(auth=auth)
        client = client_3.Client(session=session)
    else:
        auth = v2.Password(**password_creds)
        session = ks_session.Session(auth=auth)
        client = client_2_0.Client(session=session)

    context = neutron_context.get_admin_context()
    context.auth_token = client.ec2.client.get_token()
    context.user_id = client.ec2.client.get_user_id()
    context.tenant_id = client.ec2.client.get_project_id()

    grid_manager = grid.GridManager(context)
    grid_manager.sync(force_sync=True)

    credentials['session'] = session
    for key in ('user_domain_id', 'project_domain_id'):
        credentials.pop(key, None)

    sync_neutron_to_infoblox(context, credentials, grid_manager)


def register_keystone_opts(conf):
    ka_opts = [
        cfg.StrOpt('auth_uri',
                   default='',
                   help=_('Keystone Authtoken URI')),
    ]

    conf.register_group(cfg.OptGroup(
        name='keystone_authtoken',
        title='Keystone Authtoken'))
    conf.register_opts(ka_opts, group='keystone_authtoken')


def get_credentials():
    d = dict()
    version = '2'
    if 'OS_IDENTITY_API_VERSION' in os.environ:
        version = os.environ['OS_IDENTITY_API_VERSION']
    if version == '3':
        d['project_name'] = os.environ['OS_PROJECT_NAME']
        d['user_domain_id'] = os.environ.get('OS_USER_DOMAIN_ID', 'default')
        d['project_domain_id'] = os.environ.get('OS_PROJECT_DOMAIN_ID',
                                                'default')
    else:
        d['tenant_name'] = os.environ['OS_TENANT_NAME']
    d['username'] = os.environ['OS_USERNAME']
    d['password'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['region_name'] = os.environ['OS_REGION_NAME']

    return d, version


def sync_neutron_to_infoblox(context, credentials, grid_manager):
    """Sync neutron objects to Infoblox grid

    Prerequisites:
        1. network views to sync must have "Cloud Adapter ID" EA set.
        2. infoblox agent sync should have been processed and updated members
           and network views.
    """
    LOG.info("Starting migration...\n")

    delete_unknown_ips = cfg.CONF.delete_unknown_ips

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
                                  session=credentials['session'])

    instance_names_by_instance_id = dict()
    instance_names_by_floating_ip = dict()
    for server in nova_api.servers.list(search_opts={'all_tenants': 1}):
        instance_names_by_instance_id[server.id] = server.name
        floating_ips = []
        for net in server.addresses:
            floating_ips += [ip['addr'] for ip in server.addresses[net]
                             if ip['OS-EXT-IPS:type'] == 'floating']
        for fip in floating_ips:
            instance_names_by_floating_ip[fip] = server.name

    user_id = neutron_api.httpclient.get_user_id()
    user_tenant_id = neutron_api.httpclient.get_project_id()

    ib_networks = []
    should_exit = False

    # sync subnets
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
        ib_cxt = ib_context.InfobloxContext(context, user_id,
                                            network, subnet,
                                            grid_config,
                                            plugin=neutron_api)
        db_mapped_netview = dbi.get_network_view_by_mapping(
            session,
            grid_id=grid_id,
            network_id=network_id,
            subnet_id=subnet_id)
        if db_mapped_netview:
            LOG.info("Mapping found for network (%s), subnet (%s)",
                     network_name, subnet_name)
            if len(db_mapped_netview) > 1:
                LOG.warning("More that one db_mapped_netview returned")
            if delete_unknown_ips:
                ib_network = ib_objects.Network.search(
                    ib_cxt.connector,
                    network_view=db_mapped_netview[0].network_view,
                    cidr=subnet.get('cidr'))
                ib_networks.append(ib_network)
            continue

        ipam_controller = ipam.IpamSyncController(ib_cxt)
        dns_controller = dns.DnsController(ib_cxt)

        rollback_list = []
        try:
            ib_network = ipam_controller.create_subnet(rollback_list)
            if ib_network:
                if delete_unknown_ips:
                    ib_networks.append(ib_network)
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

    # sync ports
    for port in ports:
        port_id = port['id']
        port_name = port['name']
        port_mac_address = port['mac_address']
        tenant_id = port.get('tenant_id') or user_tenant_id
        network_id = port['network_id']
        device_owner = port['device_owner']
        device_id = port['device_id']

        instance_name = (instance_names_by_instance_id[device_id]
                         if device_id in instance_names_by_instance_id
                         else None)

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
                                              return_fields=['objects'],
                                              force_proxy=True)
            if ib_address and ib_address[0]['objects']:
                LOG.info("%s is found...no need to create", ip_address)
                continue

            ipam_controller = ipam.IpamSyncController(ib_cxt)
            dns_controller = dns.DnsController(ib_cxt)

            # for a floating ip port, check for its association.
            # if associated, then port info needs to be the associated port,
            # not the floating ip port because the associated port contains
            # actual attached device info
            is_floating_ip = False
            if ip_address in instance_names_by_floating_ip:
                db_floatingip = dbi.get_floatingip_by_ip_address(session,
                                                                 ip_address)
                db_port = dbi.get_port_by_id(session,
                                             db_floatingip.fixed_port_id)
                port_id = db_port.id
                port_name = db_port.name
                tenant_id = db_port.tenant_id
                device_id = db_port.device_id
                device_owner = db_port.device_owner
                instance_name = instance_names_by_floating_ip[ip_address]
                is_floating_ip = True

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
                        device_owner,
                        is_floating_ip,
                        port_name)
                except Exception as e:
                    should_exit = True
                    LOG.error("Unable to allocate ip (%s): %s", ip_address, e)
                    ipam_controller.deallocate_ip(allocated_ip)
                    break

            LOG.info("Allocated %s", ip_address)

        if should_exit:
            LOG.info("Existing due to error in port creation...")
            break

    if delete_unknown_ips:
        LOG.info("Start deleting unknown Fixed IP's from Infoblox...")
        for ib_network in ib_networks:

            nw_ea = ib_network.extattrs
            # Skip network if it doesn't have EA or if EA indicates it's
            # shared or external.
            if (not nw_ea or
                    nw_ea.get('Is External') or nw_ea.get('Is Shared')):
                continue

            LOG.info("Searching for Fixed IP: network_view='%s', cidr='%s'" %
                     (ib_network.network_view, ib_network.network))
            fixed_ips = ib_objects.FixedAddress.search_all(
                ib_cxt.connector,
                network_view=ib_network.network_view,
                network=ib_network.network)

            if not fixed_ips:
                LOG.info("No FixedIP found: network_view='%s', cidr='%s'" %
                         (ib_network.network_view, ib_network.network))
                continue

            for fixed_ip in fixed_ips:
                ea = fixed_ip.extattrs
                port_id = None
                if ea:
                    port_id = ea.get('Port ID')

                # Delete Fixed IP if:
                #   - Fixed IP does not have 'Port ID' EA, or
                #   - No port_id in neutron matches 'Port ID' EA value
                if not (port_id and
                        utils.find_one_in_list('id', port_id, ports)):
                    LOG.info("Deleting Fixed IP from Infoblox: '%s'" %
                             fixed_ip)
                    fixed_ip.delete()

    LOG.info("Ending migration...")


if __name__ == "__main__":
    main()
