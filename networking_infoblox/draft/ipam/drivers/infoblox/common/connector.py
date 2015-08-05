# Copyright 2015 OpenStack LLC.
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

import functools
import requests
from requests import exceptions as req_exc
import urllib
import urlparse

from oslo_log import log as logging
from oslo_serialization import jsonutils

from neutron.ipam.drivers.infoblox.common import exceptions as ib_ex
from neutron.ipam.drivers.infoblox.common import utils as ib_utils


LOG = logging.getLogger(__name__)


def retry_neutron_exception(func):
    @functools.wraps(func)
    def callee(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except req_exc.Timeout as e:
            LOG.error(e.message)
            raise ib_ex.InfobloxTimeoutError(e)
        except req_exc.RequestException as e:
            LOG.error(_("HTTP request failed: %s"), e)
            raise ib_ex.InfobloxConnectionError(reason=e)
    return callee


class HttpClient(object):
    """Defines methods for getting, creating, updating and
    removing objects from an Infoblox server instance.
    """

    def __init__(self, condition):
        # check if condition is properly loaded
        if not condition.ready:
            return

        self.grid_members = condition.grid_members
        self.authority_member = condition.authority_member
        if self.authority_member.member_ip:
            self.authority_member_ip = self.authority_member.member_ip
        else:
            self.authority_member_ip = self.authority_member.member_ipv6

        connection = condition.grid_connection
        self.wapi_version = connection.wapi_version
        self.wapi_url = "https://%s/wapi/v%s/" % (self.authority_member_ip,
                                                  self.wapi_version)
        if hasattr(connection.wapi_cloud_user, 'name'):
            self.username = connection.wapi_cloud_user.name
            self.password = connection.wapi_cloud_user.password
        elif hasattr(connection.wapi_admin_user, 'name'):
            self.username = connection.wapi_admin_user.name
            self.password = connection.wapi_admin_user.password

        self.ssl_verify = connection.wapi_ssl_verify
        self.http_pool_connections = connection.wapi_http_pool_connections
        self.http_pool_maxsize = connection.wapi_http_pool_maxsize
        self.request_timeout = connection.wapi_http_request_timeout

        if not self.wapi_url or not self.username or not self.password:
            raise ib_ex.InfobloxConfigException(
                msg="WAPI config error. Invalid URL or credentials")

        self.cloud_api_enabled = ib_utils.is_cloud_wapi(self.wapi_version)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.http_pool_connections,
            pool_maxsize=self.http_pool_maxsize)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.auth = (self.username, self.password)
        self.session.verify = self.ssl_verify

    def _construct_url(self, relative_path, query_params=None,
                       extattrs=None):
        if query_params is None:
            query_params = {}
        if extattrs is None:
            extattrs = {}

        if not relative_path or relative_path[0] == '/':
            raise ValueError('Path in request must be relative.')
        query = ''
        if query_params or extattrs:
            query = '?'

        if extattrs:
            attrs_queries = []
            for key, value in extattrs.items():
                attrs_queries.append('*' + key + '=' + value['value'])
            query += '&'.join(attrs_queries)
        if query_params:
            if len(query) > 1:
                query += '&'
            query += urllib.urlencode(query_params)

        base_url = urlparse.urljoin(self.wapi_url,
                                    urllib.quote(relative_path))
        return base_url + query

    @staticmethod
    def _validate_obj_type_or_die(obj_type, obj_type_expected=True):
        if not obj_type:
            raise ValueError('NIOS object type cannot be empty.')
        if obj_type_expected and '/' in obj_type:
            raise ValueError('NIOS object type cannot contain slash.')

    @retry_neutron_exception
    def get_object(self, obj_type, payload=None, return_fields=None,
                   extattrs=None, proxy=False):
        """
        Retrieve a list of Infoblox objects of type 'obj_type'
        Args:
            obj_type  (str): Infoblox object type, e.g. 'network',
                            'range', etc.
            payload (dict): Payload with data to send
            return_fields (list): List of fields to be returned
            extattrs      (list): List of Extensible Attributes
        Returns:
            A list of the Infoblox objects requested
        Raises:
            InfobloxObjectNotFound
        """
        if return_fields is None:
            return_fields = []
        if extattrs is None:
            extattrs = {}

        self._validate_obj_type_or_die(obj_type, obj_type_expected=False)

        query_params = dict()
        if payload:
            query_params = payload

        if return_fields:
            query_params['_return_fields'] = ','.join(return_fields)

        # Some get requests like 'ipv4address' should be always
        # proxied to GM on Hellfire
        # If request is cloud and proxy is not forced yet,
        # then plan to do 2 request:
        # - the first one is not proxied to GM
        # - the second is proxied to GM
        urls = dict()
        urls['direct'] = self._construct_url(obj_type, query_params,
                                             extattrs)
        if self.cloud_api_enabled:
            query_params['_proxy_search'] = 'GM'
            urls['proxy'] = self._construct_url(obj_type, query_params,
                                                extattrs)

        url = urls['direct']
        if self.cloud_api_enabled and proxy:
            url = urls['proxy']

        headers = {'Content-type': 'application/json'}

        ib_object = self._get_object(obj_type, url, headers)
        if ib_object:
            return ib_object

        # if cloud api and proxy is not used, use proxy
        if self.cloud_api_enabled and not proxy:
            return self._get_object(obj_type, urls['proxy'], headers)

        return None

    def _get_object(self, obj_type, url, headers):
        r = self.session.get(url,
                             verify=self.ssl_verify,
                             timeout=self.request_timeout,
                             headers=headers)

        if r.status_code == requests.codes.UNAUTHORIZED:
            raise ib_ex.InfobloxBadWAPICredential(response='')

        if r.status_code != requests.codes.ok:
            raise ib_ex.InfobloxSearchError(
                response=jsonutils.loads(r.content),
                obj_type=obj_type,
                content=r.content,
                code=r.status_code)

        return jsonutils.loads(r.content)

    @retry_neutron_exception
    def create_object(self, obj_type, payload, return_fields=None):
        """
        Create an Infoblox object of type 'obj_type'
        Args:
            obj_type        (str): Infoblox object type,
                                  e.g. 'network', 'range', etc.
            payload       (dict): Payload with data to send
            return_fields (list): List of fields to be returned
        Returns:
            The object reference of the newly create object
        Raises:
            InfobloxException
        """
        if not return_fields:
            return_fields = []

        self._validate_obj_type_or_die(obj_type)

        query_params = dict()

        if return_fields:
            query_params['_return_fields'] = ','.join(return_fields)

        url = self._construct_url(obj_type, query_params)
        data = jsonutils.dumps(payload)
        headers = {'Content-type': 'application/json'}
        r = self.session.post(url,
                              data=data,
                              verify=self.ssl_verify,
                              timeout=self.request_timeout,
                              headers=headers)

        if r.status_code == requests.codes.UNAUTHORIZED:
            raise ib_ex.InfobloxBadWAPICredential(response='')

        if r.status_code != requests.codes.CREATED:
            raise ib_ex.InfobloxCannotCreateObject(
                response=jsonutils.loads(r.content),
                obj_type=obj_type,
                content=r.content,
                args=payload,
                code=r.status_code)

        return jsonutils.loads(r.content)

    @retry_neutron_exception
    def call_func(self, func_name, ref, payload, return_fields=None):
        if not return_fields:
            return_fields = []

        query_params = dict()
        query_params['_function'] = func_name

        if return_fields:
            query_params['_return_fields'] = ','.join(return_fields)

        url = self._construct_url(ref, query_params)

        headers = {'Content-type': 'application/json'}
        r = self.session.post(url,
                              data=jsonutils.dumps(payload),
                              verify=self.ssl_verify,
                              headers=headers)

        if r.status_code == requests.codes.UNAUTHORIZED:
            raise ib_ex.InfobloxBadWAPICredential(response='')

        if r.status_code not in (requests.codes.CREATED,
                                 requests.codes.ok):
            raise ib_ex.InfobloxFuncException(
                response=jsonutils.loads(r.content),
                ref=ref,
                func_name=func_name,
                content=r.content,
                code=r.status_code)

        return jsonutils.loads(r.content)

    @retry_neutron_exception
    def update_object(self, ref, payload, return_fields=None):
        """
        Update an Infoblox object
        Args:
            ref      (str): Infoblox object reference
            payload (dict): Payload with data to send
        Returns:
            The object reference of the updated object
        Raises:
            InfobloxException
        """
        query_params = {}
        if return_fields:
            query_params['_return_fields'] = ','.join(return_fields)

        headers = {'Content-type': 'application/json'}
        r = self.session.put(self._construct_url(ref, query_params),
                             data=jsonutils.dumps(payload),
                             verify=self.ssl_verify,
                             timeout=self.request_timeout,
                             headers=headers)

        if r.status_code == requests.codes.UNAUTHORIZED:
            raise ib_ex.InfobloxBadWAPICredential(response='')

        if r.status_code != requests.codes.ok:
            raise ib_ex.InfobloxCannotUpdateObject(
                response=jsonutils.loads(r.content),
                ref=ref,
                content=r.content,
                code=r.status_code)

        return jsonutils.loads(r.content)

    @retry_neutron_exception
    def delete_object(self, ref):
        """
        Remove an Infoblox object
        Args:
            ref      (str): Object reference
        Returns:
            The object reference of the removed object
        Raises:
            InfobloxException
        """
        r = self.session.delete(self._construct_url(ref),
                                verify=self.ssl_verify,
                                timeout=self.request_timeout)

        if r.status_code == requests.codes.UNAUTHORIZED:
            raise ib_ex.InfobloxBadWAPICredential(response='')

        if r.status_code != requests.codes.ok:
            raise ib_ex.InfobloxCannotDeleteObject(
                response=jsonutils.loads(r.content),
                ref=ref,
                content=r.content,
                code=r.status_code)

        return jsonutils.loads(r.content)
