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

import requests

from oslo_log import log as logging
from oslo_serialization import jsonutils

LOG = logging.getLogger(__name__)


class EA_Def_Manager(object):

    def __init__(self, grid_info):
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=grid_info['http_pool_connections'],
            pool_maxsize=grid_info['http_pool_maxsize'])
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        self._session.auth = (grid_info['admin_user_name'],
                              grid_info['admin_password'])
        self._session.verify = grid_info['ssl_verify']
        self._session.timeout = grid_info['http_request_timeout']
        self._headers = {"Content-type": "application/json"}

        self._ea_def_url = ("https://%s/wapi/v%s/extensibleattributedef" %
                            (grid_info['grid_master_host'],
                             grid_info['wapi_version']))

    def get_existing_ea_defs(self):
        # Sends request with Authentication Information
        r = self._session.get(self._ea_def_url, headers=self._headers)

        if r.status_code != requests.codes.ok:
            LOG.error(
                "Cannot get EA Definitions from Grid '%s' (error code: '%s')" %
                (self._ea_def_url, r.status_code))
        self._existing_ea_defs = jsonutils.loads(r.content)
        return self._existing_ea_defs

    def find_missing_ea_defs(self, target_ea_defs, existing_ea_defs=None):

        if not existing_ea_defs:
            existing_ea_defs = self._existing_ea_defs
        self._missing_ea_defs = filter(lambda x: not next(
            (y for y in existing_ea_defs if x['name'] == y['name']), None),
            target_ea_defs)
        return self._missing_ea_defs

    def create_ea_def(self, ea_def):
        r = self._session.post(self._ea_def_url, data=jsonutils.dumps(ea_def),
                               headers=self._headers)
        if (r.status_code != requests.codes.ok and
                r.status_code != requests.codes.CREATED):
            LOG.error(
                "Cannot create EA Definition '%s' on '%s' (error code: '%s')" %
                (ea_def, self._ea_def_url, r.status_code))
            return False

        LOG.info(
            "EA Definition '%s' successfully created on '%s'. (_ref is '%s')" %
            (ea_def, self._ea_def_url, jsonutils.loads(r.content)))
        return True

    def create_missing_ea_defs(self, missing_ea_defs=None):
        if not missing_ea_defs:
            missing_ea_defs = self._missing_ea_defs

        ea_defs_created = []
        for ea_def in missing_ea_defs:
            if self.create_ea_def(ea_def):
                ea_defs_created.append(ea_def)
        return ea_defs_created
