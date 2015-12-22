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


from keystoneclient.auth import token_endpoint
from keystoneclient import session
from keystoneclient.v2_0 import client as k_client
from neutron.common import config as cfg
from oslo_log import log

CONF = cfg.cfg.CONF
LOG = log.getLogger(__name__)

_SESSION = None


def init_keystone_session():
    global _SESSION
    if not _SESSION:
        _SESSION = session.Session()


def get_keystone_client(context):
    init_keystone_session()
    url = CONF['keystone_authtoken']['auth_uri'] + '/v2.0/'
    auth = token_endpoint.Token(url, context.auth_token)
    return k_client.Client(session=session, auth=auth)


def get_all_tenants(context):
    try:
        keystone = get_keystone_client(context)
        return keystone.tenants.list()
    except Exception as e:
        LOG.warn("Could not get tenants due to error %s", e)
    return []


def get_tenant_name_by_tenant_id(context, tenant_id):
    try:
        keystone = get_keystone_client(context)
        tenant = keystone.tenants.get(tenant_id)
        return tenant.name
    except Exception as e:
        LOG.warn("Could not get tenant due to error %s", e)
