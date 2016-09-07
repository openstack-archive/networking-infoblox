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

import getpass
import os
import six
import sys

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import config as common_config

from infoblox_client import exceptions as ib_ex
from infoblox_client import object_manager
from infoblox_client import objects

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import ea_manager as eam
from networking_infoblox.neutron.common import utils


ENV_SUPERUSER_USERNAME = 'NETWORKING_INFOBLOX_SUPERUSER_USERNAME'
ENV_SUPERUSER_PASSWORD = 'NETWORKING_INFOBLOX_SUPERUSER_PASSWORD'
ENV_NETWORK_VIEW_PARTICIPATION_LIST = (
    'NETWORKING_INFOBLOX_DC_PARTICIPATING_NETWORK_VIEWS')

PRINT_LINE = 80

LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.BoolOpt('script',
                short='s',
                default=False,
                help='scripting mode'),
    cfg.StrOpt('username',
               short='u',
               help='username of superuser'),
    cfg.StrOpt('password',
               short='p',
               help='password of superuser'),
    cfg.StrOpt('participating_network_views',
               short='pnv',
               help='participating network views')
]

cfg.CONF.register_cli_opts(cli_opts)
cfg.CONF(args=sys.argv[1:])


def main():
    cfg.CONF(args=sys.argv[1:],
             default_config_files=['/etc/neutron/neutron.conf'])
    common_config.setup_logging()
    config.register_infoblox_ipam_opts(cfg.CONF)
    grid_id = cfg.CONF.infoblox.cloud_data_center_id
    config.register_infoblox_grid_opts(cfg.CONF, grid_id)

    create_ea_defs(grid_id)
    participate_network_views(grid_id)


def get_credentias():
    credentials = None
    # User command line arguments if specified
    if cfg.CONF.username and cfg.CONF.password:
        credentials = {'username': cfg.CONF.username,
                       'password': cfg.CONF.password}

    # Use environment variable if found
    if not credentials:
        if (ENV_SUPERUSER_USERNAME in os.environ and
                ENV_SUPERUSER_PASSWORD in os.environ):
            username = os.environ[ENV_SUPERUSER_USERNAME]
            password = os.environ[ENV_SUPERUSER_PASSWORD]
            if username and password:
                credentials = {'username': username, 'password': password}

    if not credentials and not cfg.CONF.script:
        print("In order to create Extensible Attribute definitions,")
        print("superuser privilege is required.\n")
        print("If the preconfigured credentials already has superuser ")
        print("privilege, just hit <ENTER> when prompted for user name.\n")
        print("Otherwise, please enter user name and password of a user that "
              "has superuser privilege.\n")
        username = raw_input("Enter user name: ")
        if len(username) > 0:
            password = getpass.getpass("Enter password: ")
            credentials = {'username': username, 'password': password}
        print("\n")
    return credentials


def create_ea_defs(grid_id):
    print("\nCreating EA definitions...")
    print("-" * PRINT_LINE)
    print("")

    credentials = get_credentias()
    conn = utils.get_connector(credentials)

    if not (utils.get_features(conn).create_ea_def):
        LOG.error("WAPI Version '%s' is not supported - Script ABORTED!",
                  conn.wapi_version)
        exit(1)

    mgr = object_manager.InfobloxObjectManager(conn)
    ea_defs_created = mgr.create_required_ea_definitions(
        const.REQUIRED_EA_DEFS, reraise=True)
    if ea_defs_created:
        print("The following EA Definitions have been created: '%s'" %
              [ea_def['name'] for ea_def in ea_defs_created])
    else:
        print("All the EAs has been already created.")
    print("\n")

    grid_opts = config.get_infoblox_grid_opts(grid_id)
    gm_name = grid_opts['grid_master_name']
    member = objects.Member.search(conn, host_name=gm_name)

    if member is None:
        LOG.error("Cannot retrieve member information at GM='%s'" %
                  gm_name)
        exit(1)

    print("Adding grid configuration EAs to the grid master...")
    print("-" * PRINT_LINE)
    print("")
    ea_set = {}
    if member.extattrs is None:
        member.extattrs = objects.EA({})
    for ea, val in const.GRID_CONFIG_DEFAULTS.items():
        if (member.extattrs.get(ea) is None and
                not (val is None or val == [])):
            ea_set[ea] = val
            member.extattrs.set(ea, val)

    if ea_set:
        print("Grid configurations: '%s'" % ea_set)
        member.update()
    else:
        print("All the grid configurations have been already added.")
    print("\n")


def participate_network_views(grid_id):
    print("Associating/Unassociating network views for OpenStack...")
    print("-" * PRINT_LINE)
    print("")

    netview_input = None
    if cfg.CONF.participating_network_views:
        netview_input = cfg.CONF.participating_network_views
    elif ENV_NETWORK_VIEW_PARTICIPATION_LIST in os.environ:
        netview_input = os.environ[ENV_NETWORK_VIEW_PARTICIPATION_LIST]

    grid_id_str = str(grid_id)
    conn = utils.get_connector()

    ib_netviews = objects.NetworkView.search_all(conn)
    if not ib_netviews:
        print("No network view exists\n")
        return

    netview_names = [ib_netview.name for ib_netview in ib_netviews]
    print("Found %s network views from the grid.\n" % len(netview_names))

    operation = 'ASSOCIATION'
    if not netview_input and not cfg.CONF.script:
        expected_answers_operation = ['a', 'u']
        expected_answers_yes_no = ['y', 'n']

        question = ("Please type 'a' to associate network views, 'u' to "
                    "unassociate.")
        choice = ask_question(question, expected_answers_operation)
        operation = 'ASSOCIATION' if choice == 'a' else 'UNASSOCIATION'

        question = "Do you want to list network views?"
        choice = ask_question(question, expected_answers_yes_no)
        if choice == 'y':
            print(', '.join(netview_names))
            print("")
        question = "Please provide a comma separated list of network views: "
        netview_input = raw_input(question)

    if (not netview_input or
            not isinstance(netview_input, six.string_types)):
        msg = ("Participating network views should be in the "
               "comma-delimited string format.")
        if cfg.CONF.script:
            LOG.warning(msg)
        else:
            print(msg)
        return

    netview_list = []
    [netview_list.append(x.strip()) for x in netview_input.split(',')
     if x and x not in netview_list]
    if not netview_list:
        print("")
        return

    for nv in netview_list:
        ib_netview_found = [ib_net for ib_net in ib_netviews
                            if ib_net.name == nv]
        if not ib_netview_found:
            print("'%s' is not found." % nv)
            continue

        ib_netview = ib_netview_found[0]
        ea_netview = eam.get_ea_for_network_view(None, None, grid_id)
        if operation == 'ASSOCIATION':
            if ib_netview.extattrs is None:
                ib_netview.extattrs = ea_netview
            else:
                cloud_adapter_ids = ib_netview.extattrs.get(
                    const.EA_CLOUD_ADAPTER_ID)
                if cloud_adapter_ids:
                    if isinstance(cloud_adapter_ids, six.string_types):
                        cloud_adapter_ids = [cloud_adapter_ids]

                    found_ids = [id for id in cloud_adapter_ids
                                 if id == grid_id_str]
                    if found_ids:
                        print("'%s' already associated." % nv)
                        continue

                    cloud_adapter_ids.append(grid_id_str)
                else:
                    cloud_adapter_ids = [grid_id_str]

                ib_netview.extattrs.set(const.EA_CLOUD_ADAPTER_ID,
                                        cloud_adapter_ids)
            try:
                ib_netview.update()
            except ib_ex.InfobloxCannotUpdateObject as e:
                if 'Write permission' in e.msg:
                    print("'%s' has no write permission." % nv)
                    continue
                else:
                    print("'%s' failed to associate: %s" % (nv, e.msg))
                    continue
            print("'%s' is now associated." % nv)
        else:
            if ib_netview.extattrs is None:
                print("'%s' not associated." % nv)
                continue

            cloud_adapter_ids = ib_netview.extattrs.get(
                const.EA_CLOUD_ADAPTER_ID)
            if cloud_adapter_ids:
                if isinstance(cloud_adapter_ids, six.string_types):
                    cloud_adapter_ids = [cloud_adapter_ids]

                found_ids = [id for id in cloud_adapter_ids
                             if id == grid_id_str]
                if found_ids:
                    cloud_adapter_ids.remove(grid_id_str)
                    ib_netview.extattrs.set(const.EA_CLOUD_ADAPTER_ID,
                                            cloud_adapter_ids)
                    try:
                        ib_netview.update()
                    except ib_ex.InfobloxCannotUpdateObject as e:
                        if 'Write permission' in e.msg:
                            print("'%s' has no write permission." % nv)
                            continue
                        else:
                            print("'%s' failed to unassociated: %s" %
                                  (nv, e.msg))
                            continue
                    print("'%s' is now unassociated." % nv)
                else:
                    print("'%s' not associated." % nv)
            else:
                print("'%s' not associated." % nv)

    print("\n")


def ask_question(question, expected_answers):
    prompt_choice = ["'%s'" % ans for ans in expected_answers]
    prompt_choice = " or ".join(prompt_choice)

    while True:
        choice = raw_input("%s Enter %s: " % (question, prompt_choice))
        if choice not in expected_answers:
            print("Enter a valid choice. Please try again.\n")
            continue
        else:
            break
    print("")
    return choice


if __name__ == "__main__":
    main()
