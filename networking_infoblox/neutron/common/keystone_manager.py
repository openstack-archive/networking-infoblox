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

from keystoneclient.auth.identity.generic import token
from keystoneclient.auth import token_endpoint
from keystoneclient import session
from keystoneclient.v2_0 import client as client_2_0
from keystoneclient.v3 import client as client_3
from neutron.common import config as cfg

from oslo_config import cfg as os_cfg
from oslo_log import log

from networking_infoblox.neutron.db import infoblox_db as dbi


CONF = cfg.cfg.CONF


LOG = log.getLogger(__name__)
_SESSION = None


def register_keystone_opts(conf):
    ka_opts = [
        os_cfg.StrOpt('auth_uri',
                      default='',
                      help=_('Keystone Authtoken URI')),
        os_cfg.StrOpt('admin_user',
                      help='Admin user name'),
        os_cfg.StrOpt('admin_password',
                      help='Admin password'),
        os_cfg.StrOpt('admin_tenant_name',
                      help='Admin tenant name'),
        os_cfg.StrOpt('project_domain_id',
                      help='Admin Project domain id'),
        os_cfg.StrOpt('auth_version',
                      default='v2.0', help='Auth protocol used.'),
    ]
    conf.register_group(os_cfg.OptGroup(
        name='keystone_authtoken',
        title='Keystone Authtoken'))
    conf.register_opts(ka_opts, group='keystone_authtoken')

if 'keystone_authtoken' not in CONF:
    LOG.warn("Keystone Authtoken not registered in opts,registering...")
    register_keystone_opts(CONF)


def init_keystone_session():
    global _SESSION
    if not _SESSION:
        _SESSION = session.Session()
    return _SESSION


def get_identity_service(keystone_conf):
    allowed_keystone_version = ['v2.0', 'v3']
    uri_version = keystone_conf.auth_uri.split('/')[-1]
    if uri_version in allowed_keystone_version:
        return keystone_conf.auth_uri, uri_version
    return (keystone_conf.auth_uri + (
        '/%s' % (keystone_conf.auth_version)),
        keystone_conf.auth_version)


def get_keystone_client(auth_token):
    key_client = None
    keystone_conf = CONF.keystone_authtoken
    identity_service, version = get_identity_service(keystone_conf)
    if version == 'v2.0':
        key_client = get_keystone_client_v2(auth_token)

    elif version == 'v3':
        key_client = (
            client_3.Client(
                username=keystone_conf.admin_user,
                password=keystone_conf.admin_password,
                domain_name=keystone_conf.project_domain_id,
                auth_url=identity_service))

    return key_client


def get_keystone_client_v2(auth_token):
    sess = init_keystone_session()
    url = CONF.keystone_authtoken.auth_uri
    # Create token to get available service version
    generic_token = token.Token(url, token=auth_token)
    generic_token.reauthenticate = False
    version = generic_token.get_auth_ref(sess)['version']
    # update auth url aith version if needed
    if version not in url.split('/'):
        url = url + '/' + version
    # create endpoint token using right url and provided auth token
    auth = token_endpoint.Token(url, auth_token)
    k_client = client_2_0.Client(session=sess, auth=auth)
    return k_client


def get_all_tenants(auth_token):
    try:
        keystone = get_keystone_client(auth_token)
        if keystone.version == 'v3':
            return keystone.projects.list()
        else:
            return keystone.tenants.list()
    except Exception as e:
        LOG.warning("Could not get tenants due to error: %s", e)
    return []


def update_tenant_mapping(context, networks, tenant_id,
                          tenant_name, auth_token):
    """Updates tenant_id to tenant_name mapping information.

    Tries to get tenant name to tenant id mapping from context info.
    If context tenant id is different from network tenant_id,
    then check if id to name mapping is already known (check db).
    If id to name mapping still unknown run API call to keystone to
    get all known tenants and store this mapping.
    """

    dbi.add_or_update_tenant(context.session, tenant_id, tenant_name)

    # If there are no auth_token all later checks are useless
    if not auth_token:
        return

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
        # If there are still unknown tenants in request try last resort
        # make an api call to keystone with auth_token
        if _get_unknown_ids_from_dict(tenant_ids):
            sync_tenants_from_keystone(context, auth_token)


def _get_unknown_ids_from_dict(tenant_ids):
    return [id for id, unknown in tenant_ids.items()
            if unknown is True]


def sync_tenants_from_keystone(context, auth_token):
    if not auth_token:
        return

    tenants = get_all_tenants(auth_token)
    for tenant in tenants:
        LOG.info("Tenants obtained from keystone: %s", tenant)
        # tenants from keystone have 'id' and 'name' comparing to
        # db cache where 'tenant_id' and 'tenant_name' are used
        dbi.add_or_update_tenant(context.session, tenant.id, tenant.name)
    return len(tenants)
