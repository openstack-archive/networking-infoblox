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


from keystoneclient.auth.identity.generic import password
from keystoneclient.auth import token_endpoint
from keystoneclient import session
from keystoneclient.v2_0 import client as k_client
from oslo_config import cfg
from oslo_log import log

from networking_infoblox.neutron.common import mini_cache

CONF = cfg.CONF
LOG = log.getLogger(__name__)

_SESSION = None
_CACHE = None


def init_cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = mini_cache.MiniCache()


def init_keystone_session():
    global _SESSION
    if not _SESSION:
        _SESSION = session.Session()


def get_keystone_client(context):
    init_keystone_session()
    auth = token_endpoint.Token(CONF.keystone_authtoken.auth_uri + '/v2.0/',
                                context.auth_token)
    LOG.error(_("Auth info: %s"), (CONF.keystone_authtoken.auth_url,
              CONF.keystone_authtoken.auth_uri, context.auth_token))
    return k_client.Client(session=_SESSION, auth=auth)


def get_keystone_admin_client(tenant_id):
    init_keystone_session()
    admin_auth = password.Password(
        auth_url=CONF.keystone_authtoken.auth_uri,
        username=CONF.keystone_authtoken.username,
        password=CONF.keystone_authtoken.password,
        tenant_name=tenant_id #CONF.keystone_authtoken.admin_tenant_name
        )
    return k_client.Client(session=_SESSION, auth=admin_auth)


def get_tenant_name_by_tenant_id(tenant_id, context=None):
    init_cache()
    if _CACHE.get(tenant_id):
        return _CACHE.get(tenant_id)

    keystone = get_keystone_client(context)
    #keystone = get_keystone_admin_client(tenant_id)
    try:
        LOG.error(_("Tenant ID incom: %s"), tenant_id)
        tenant_list = keystone.tenants.list()
        LOG.error("ALL Tenants: %s", tenant_list)
        if tenant_list:
           for tenant in tenant_list:
              if tenant.id == tenant_id:
                  LOG.error("Found Tenant: %s", tenant)
                  _CACHE.set(tenant_id, tenant.name)
                  return tenant.name
    except Exception as e:
        LOG.error(_("Tenant not found: %s"), e)
    return tenant_id

