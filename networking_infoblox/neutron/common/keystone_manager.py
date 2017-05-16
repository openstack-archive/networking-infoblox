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

from keystoneauth1.identity import generic
from keystoneauth1 import loading

from keystoneclient.v2_0 import client as client_2_0
from keystoneclient.v3 import client as client_3

# from neutron.common import config as cfg
from oslo_config import cfg
from oslo_log import log

from networking_infoblox.neutron.db import infoblox_db as dbi


CONF = cfg.CONF


LOG = log.getLogger(__name__)


def get_identity_service(ib_opts):
    allowed_keystone_version = ['v2.0', 'v3']
    uri_version = ib_opts.keystone_auth_uri.split('/')[-1]
    if uri_version in allowed_keystone_version:
        return ib_opts.keystone_auth_uri, uri_version
    return (ib_opts.keystone_auth_uri + (
        '/%s' % (ib_opts.keystone_auth_version)),
        (ib_opts.keystone_auth_version))


def get_keystone_client():
    key_client = None
    ib_opts = CONF.infoblox
    identity_service, version = get_identity_service(ib_opts)
    auth = generic.Password(
        auth_url=identity_service,
        username=ib_opts.keystone_admin_username,
        password=ib_opts.keystone_admin_password,
        project_name=ib_opts.keystone_admin_project_name,
        user_domain_id=ib_opts.keystone_admin_user_domain_id,
        project_domain_id=ib_opts.keystone_admin_project_domain_id,
        tenant_name=ib_opts.keystone_admin_tenant_name,
        domain_id=ib_opts.keystone_admin_domain_id)

    session = loading.load_session_from_conf_options(CONF, 'infoblox',
                                                     auth=auth)

    if version == 'v2.0':
        key_client = client_2_0.Client(session=session)
    elif version == 'v3':
        key_client = client_3.Client(session=session)
    return key_client


def get_all_tenants():
    try:
        keystone = get_keystone_client()
        if keystone.version == 'v3':
            return keystone.projects.list()
        else:
            return keystone.tenants.list()
    except Exception as e:
        LOG.warning("Could not get tenants due to error: %s", e)
    return []


def update_tenant_mapping(context, networks, tenant_id,
                          tenant_name):
    """Updates tenant_id to tenant_name mapping information.

    Tries to get tenant name to tenant id mapping from context info.
    If context tenant id is different from network tenant_id,
    then check if id to name mapping is already known (check db).
    If id to name mapping still unknown run API call to keystone to
    get all known tenants and store this mapping.
    """

    dbi.add_or_update_tenant(context.session, tenant_id, tenant_name)

    # Get unique tenants ids and check if there are unknown one
    tenant_ids = {net['tenant_id']: True for net in networks}
    if tenant_id in tenant_ids:
        tenant_ids[tenant_id] = False
    unknown_ids = _get_unknown_ids_from_dict(tenant_ids)

    # There are some unknown ids, check if there are mapping in database
    if unknown_ids:
        db_tenants = dbi.get_tenants(context.session,
                                     tenant_ids=unknown_ids)
        for tenant in db_tenants:
            tenant_ids[tenant.tenant_id] = False
        if _get_unknown_ids_from_dict(tenant_ids):
            sync_tenants_from_keystone(context)


def _get_unknown_ids_from_dict(tenant_ids):
    return [id for id, unknown in tenant_ids.items()
            if unknown is True]


def sync_tenants_from_keystone(context):
    tenants = get_all_tenants()
    for tenant in tenants:
        LOG.info("Tenants obtained from keystone: %s", tenant)
        # tenants from keystone have 'id' and 'name' comparing to
        # db cache where 'tenant_id' and 'tenant_name' are used
        dbi.add_or_update_tenant(context.session, tenant.id, tenant.name)
    return len(tenants)
