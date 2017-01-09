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

import datetime
import decimal
import hashlib
import netaddr
import random
import re
import six
import time
import urllib

from oslo_serialization import jsonutils

from infoblox_client import connector as conn
from infoblox_client import feature
from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import config as cfg
from networking_infoblox.neutron.common import constants as const


def json_to_obj(obj_type, json_data):
    """Converts json data to an object with a given object type

    :param obj_type: converted object's type that is determined dynamically
    :param json_data: json string or json object
    :return: object
    """
    def dic2obj(x):
        if isinstance(x, dict):
            return type(obj_type, (),
                        {k: dic2obj(v) for k, v in six.iteritems(x)})
        else:
            return x

    if isinstance(json_data, six.string_types):
        json_data = jsonutils.loads(json_data)
    return dic2obj(json_data)


def get_values_from_records(key, records):
    key_vals = []
    if records is None:
        return key_vals

    for record in records:
        key_val = record.get(key, None)
        if key_val:
            key_vals.append(key_val)
    return key_vals


def get_composite_values_from_records(keys, records, delimiter='^'):
    key_vals = []
    if records is None:
        return key_vals

    for record in records:
        values = []
        for key in keys:
            key_val = record.get(key)
            if key_val:
                if not isinstance(key_val, six.string_types):
                    key_val = str(key_val)
                values.append(key_val)
        key_vals.append(delimiter.join(values))
    return key_vals


def db_records_to_obj(obj_type, records):
    record_json = db_records_to_json(records)
    if not isinstance(record_json, list):
        return json_to_obj(obj_type, record_json)

    result_set = []
    for record in records:
        result_set.append(json_to_obj(obj_type, record))
    return result_set


def db_records_to_json(records):
    """Converts db records to json.

    alchemy_encoder is needed for date and numeric(x,y) fields since
    they will turn into datetime.date and decimal.Decimal types.
    """
    def alchemy_encoder(obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)

    rows = []
    for record in records:
        if isinstance(record, tuple):
            merge = dict()
            for table in record:
                merge.update(dict(table))
            rows.append(merge)
        else:
            rows.append(dict(record))

    # return all rows as a JSON array of objects
    json_str = jsonutils.dumps(rows, alchemy_encoder)
    return jsonutils.loads(json_str)


def get_string_or_none(value):
    ret_val = None
    if isinstance(value, six.string_types):
        ret_val = value
    else:
        if value is not None:
            ret_val = str(value)
    return ret_val


def get_ea_value(name, extattrs, should_return_list_value=False):
    valid = (name and isinstance(name, six.string_types) and
             extattrs and isinstance(extattrs, dict))
    if not valid:
        return None

    value = None
    if extattrs:
        root = extattrs.get("extattrs")
        if root:
            name_attr = root.get(name)
            if name_attr:
                value = name_attr.get('value')
                if should_return_list_value and not isinstance(value, list):
                    value = [value]
    return value


def reset_required_eas(ib_obj):
    if not ib_obj or not ib_obj.extattrs or not ib_obj.extattrs.to_dict():
        return

    for ea in const.REQUIRED_EA_LIST:
        if ea == const.EA_CLOUD_API_OWNED:
            ib_obj.extattrs.set(ea, 'False')
        else:
            ib_obj.extattrs.set(ea, const.EA_RESET_VALUE)


def get_ip_version(ip_address):
    valid = ip_address and isinstance(ip_address, six.string_types)
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if type(ip_address) is dict:
        ip = ip_address['ip_address']
    else:
        ip = ip_address

    try:
        ip = netaddr.IPAddress(ip)
    except ValueError:
        ip = netaddr.IPNetwork(ip)
    return ip.version


def is_valid_ip(ip):
    try:
        netaddr.IPAddress(ip)
    except netaddr.core.AddrFormatError:
        return False
    return True


def generate_duid(mac):
    """DUID is consisted of 10 hex numbers.

    0x00 + 3 random hex + mac with 6 hex
    """
    valid = mac and isinstance(mac, six.string_types)
    if not valid:
        raise ValueError("Invalid argument was passed.")
    duid = [0x00,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, duid)) + ':' + mac


def get_list_from_string(data_string, delimiter_list):
    valid = (data_string and
             isinstance(data_string, six.string_types) and
             delimiter_list and
             isinstance(delimiter_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    list_data = remove_any_space(data_string)
    if isinstance(delimiter_list, six.string_types):
        if len(delimiter_list) == 0:
            return data_string
        return list_data.split(delimiter_list)

    if isinstance(delimiter_list, list):
        delimiter_count = len(delimiter_list)
        if delimiter_count == 0:
            return data_string
        if delimiter_count == 1:
            return list_data.split(delimiter_list[0])
        if delimiter_count > 2:
            return ValueError("Delimiter list can contain up to 2 delimiters.")

        result_list = []
        for delimiter in delimiter_list:
            if isinstance(list_data, six.string_types):
                list_data = list_data.split(delimiter)
            else:
                for ld in list_data:
                    result_list.append(ld.split(delimiter))
        # clean up empty string element ['']
        result_list[0] = [m for m in result_list[0] if m]
        result_list[1] = [m for m in result_list[1] if m]
        return result_list

    raise ValueError("Unsupported delimiter list type.")


def exists_in_sequence(sub_sequence_to_find, full_list_in_sequence):
    valid = (isinstance(sub_sequence_to_find, list) and
             isinstance(full_list_in_sequence, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not sub_sequence_to_find or not full_list_in_sequence:
        return False

    return any(full_list_in_sequence[pos:pos + len(sub_sequence_to_find)] ==
               sub_sequence_to_find for pos in
               range(0,
                     len(full_list_in_sequence) -
                     len(sub_sequence_to_find) + 1))


def exists_in_list(list_to_find, full_list):
    valid = isinstance(list_to_find, list) and isinstance(full_list, list)
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not list_to_find or not full_list:
        return False

    found_list = [m for m in list_to_find if m in full_list]
    return len(found_list) == len(list_to_find)


def find_one_in_list(search_key, search_value, search_list):
    """Find one item that match searching one key and value."""
    valid = (isinstance(search_key, six.string_types) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not search_key or not search_value or not search_list:
        return None

    found_list = [m for m in search_list if m.get(search_key) == search_value]
    return found_list[0] if found_list else None


def find_in_list_by_condition(search_key_value_pairs, search_list):
    """Find one item that match given search key value pairs.

    :param search_key_value_pairs: dictionary that contains search key and
    values
    :param search_list: list of dictionary objects to search
    :return: a single item that matches criteria or None
    """
    valid = (isinstance(search_key_value_pairs, dict) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not search_key_value_pairs or not search_list:
        return None

    results = []
    for m in search_list:
        match_failed = False
        for key in search_key_value_pairs:
            if not m.get(key) == search_key_value_pairs[key]:
                match_failed = True
                break
        if not match_failed:
            results.append(m)
    return results


def find_in_list(search_key, search_values, search_list):
    """Find items that match multiple search values on a single search key.

    :param search_key: a key to search
    :param search_values: values that match
    :param search_list: list of dictionary objects to search
    :return: list that matches criteria
    """
    valid = (isinstance(search_key, six.string_types) and
             isinstance(search_values, list) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not search_key or not search_values or not search_list:
        return None

    found_list = [m for m in search_list if m.get(search_key) in search_values]
    return found_list


def find_in_list_by_value(search_value, search_list,
                          first_occurrence_only=True):
    """Find item(s) that match(es) the search value from the search list."""
    valid = isinstance(search_list, list)
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not search_value or not search_list:
        return None

    if isinstance(search_list[0], dict):
        found_list = [m for m in search_list if search_value in m.values()]
    else:
        found_list = [m for m in search_list
                      if search_value in m.__dict__.values()]

    if first_occurrence_only:
        return found_list[0] if found_list else None
    return found_list


def find_key_from_list(search_key, search_list):
    """Find items that contain a search key.

    :param search_key: a key to search
    :param search_list: list of dictionary objects to search
    :return: list that matches criteria
    """
    valid = (isinstance(search_key, six.string_types) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed.")

    if not search_key or not search_list:
        return None

    found_list = [m for m in search_list
                  if isinstance(m, dict) and m.get(search_key)]
    return found_list


def merge_list(*list_args):
    merge_lsit = []
    for lst in list_args:
        if not isinstance(lst, list):
            raise ValueError("Invalid argument was passed.")
        merge_lsit += lst
    return list(set(merge_lsit))


def remove_any_space(text):
    if text:
        return re.sub(r'\s+', '', text)
    return text


def get_hash(text=None):
    if text and isinstance(text, six.string_types):
        text = text.encode('utf-8')
        return hashlib.md5(text).hexdigest()
    return hashlib.md5(str(time.time())).hexdigest()


def get_oid_from_nios_ref(obj_ref):
    if obj_ref and isinstance(obj_ref, six.string_types) and len(obj_ref) > 0:
        match = re.search('\S+\/(\S+):(\S+)', obj_ref)
        if match:
            return match.group(1)
    return None


def get_network_view_id(grid_id, obj_ref):
    if grid_id and obj_ref:
        obj_id = get_oid_from_nios_ref(obj_ref)
        if obj_id:
            return "%s:%s" % (grid_id, obj_id)
    return None


def get_network_info_from_nios_ref(network_ref):
    if network_ref and len(network_ref) > 0:
        match = re.search('(\S+)\/(\S+):(\S+)\/(\d+)\/(\S+)', network_ref)
        if match:
            cidr = match.group(3) + '/' + match.group(4)
            if match.group(1) == 'ipv6network':
                cidr = urllib.unquote(cidr)
            return {'object_id': match.group(2),
                    'network_view': match.group(5),
                    'cidr': cidr}
    return None


def get_member_status(node_status):
    member_status = const.MEMBER_STATUS_OFF
    if node_status == const.MEMBER_NODE_STATUS_FAILED:
        member_status = const.MEMBER_STATUS_OFF
    elif node_status == const.MEMBER_NODE_STATUS_INACTIVE:
        member_status = const.MEMBER_STATUS_OFF
    elif node_status == const.MEMBER_NODE_STATUS_WARNING:
        member_status = const.MEMBER_STATUS_ON
    elif node_status == const.MEMBER_NODE_STATUS_WORKING:
        member_status = const.MEMBER_STATUS_ON
    return member_status


def get_notification_handler_name(event_type):
    service, resource, action, sequence = (None, None, None, None)
    if event_type.count('.') == 2:
        resource, action, sequence = event_type.split('.', 2)
    else:
        service, resource, action, sequence = event_type.split('.', 3)

    event_sequence = 'alert' if sequence == 'start' else 'sync'
    handler_name = "%s_%s_%s" % (action, resource, event_sequence)
    return handler_name


def generate_network_view_name(object_id, object_name=None):
    """Generates Network View name by id and name.

    Truncates generated network view to do not exceed allowed length of 64
    characters for network_view. dns_view can be generated from network_view
    by prepending 'default.', so limit max allowed length for network view
    by 64 - len('default.') = 56.
    """
    if not object_id or not isinstance(object_id, six.string_types):
        raise ValueError("object_id cannot be empty and must a string.")

    if object_name and not isinstance(object_name, six.string_types):
        raise ValueError("object name must be a string.")

    netview_name = ("{}-{}".format(object_name, object_id)
                    if object_name else object_id)

    if len(netview_name) > const.NETVIEW_MAX_LEN:
        return netview_name[:const.NETVIEW_MAX_LEN]
    return netview_name


def get_connector(credentials=None):
    grid_id = cfg.CONF.infoblox.cloud_data_center_id
    grid_opts = cfg.get_infoblox_grid_opts(grid_id)
    # map connector options to config
    # None as value means no name change needed
    mapping = {'host': 'grid_master_host',
               'username': 'admin_user_name',
               'password': 'admin_password',
               'wapi_version': None,
               'ssl_verify': None,
               'http_pool_connections': None,
               'http_pool_maxsize': None,
               'http_request_timeout': None}
    opts = {field: grid_opts[mapping[field]]
            if mapping[field] else grid_opts[field]
            for field in mapping}
    if opts['ssl_verify'] == 'False':
        opts['silent_ssl_warnings'] = True
    if credentials:
        opts['username'] = credentials['username']
        opts['password'] = credentials['password']
    return conn.Connector(opts)


def get_ipv4_network_prefix(cidr, subnet_name):
    """Add prefix for an ipv4 classless network mask greater than 24."""
    valid = cidr and isinstance(cidr, six.string_types)
    if not valid:
        raise ValueError("Invalid argument was passed.")

    try:
        ip_net = netaddr.IPNetwork(cidr)
    except netaddr.core.AddrFormatError:
        raise ValueError("Invalid cidr")

    if ip_net.version != 4:
        return None

    prefix = None
    if ip_net.prefixlen > 24:
        if subnet_name and len(subnet_name) > 0:
            prefix = subnet_name
        else:
            prefix = '-'.join(filter(None, re.split(r'[.:/]', cidr)))
    return prefix


def get_features(version, feature_versions=None):
    if feature_versions is None:
        feature_versions = const.FEATURE_VERSIONS
    return feature.Feature(version, feature_versions=feature_versions)


def get_dhcp_member_ips(ib_network):
    """Get dhcp member ips from network json or ib network object."""
    member_ips = []
    if (not ib_network or not (isinstance(ib_network, dict) or
                               isinstance(ib_network, ib_objects.Network))):
        return member_ips

    if isinstance(ib_network, dict):
        if ib_network.get('members'):
            for member in ib_network['members']:
                if member.get('_struct') == 'dhcpmember':
                    member_ip = (member.get('ipv4addr') or
                                 member.get('ipv6addr'))
                    if member_ip:
                        member_ips.append(member_ip)
    else:
        if ib_network.members:
            for member in ib_network.members:
                if member._struct == 'dhcpmember':
                    member_ip = member.ipv4addr or member.ipv6addr
                    if member_ip:
                        member_ips.append(member_ip)
    return member_ips


def get_dns_member_ips(ib_network):
    """Get dns member ips from network json or ib network object."""
    member_ips = []
    if (not ib_network or not (isinstance(ib_network, dict) or
                               isinstance(ib_network, ib_objects.Network))):
        return member_ips

    if isinstance(ib_network, dict):
        if ib_network.get('options'):
            for option in ib_network['options']:
                if option.get('name') == 'domain-name-servers':
                    option_values = option.get('value')
                    if option_values:
                        member_ips = option_values.split(',')
                    break
    else:
        for option in ib_network.options:
            if option.name == 'domain-name-servers':
                if option.value:
                    member_ips = option.value.split(',')
                break
    return member_ips


def get_router_ips(ib_network):
    """Get gateway ips (routers) from network json or ib network object."""
    router_ips = []
    if (not ib_network or not (isinstance(ib_network, dict) or
                               isinstance(ib_network, ib_objects.Network))):
        return router_ips

    if isinstance(ib_network, dict):
        if ib_network.get('options'):
            for option in ib_network['options']:
                if option.get('name') == 'routers':
                    option_values = option.get('value')
                    if option_values:
                        router_ips = option_values.split(',')
                    break
    else:
        for option in ib_network.options:
            if option.name == 'routers':
                if option.value:
                    router_ips = option.value.split(',')
                break
    return router_ips


def find_member_by_ip_from_list(member_ip, members):
    """Find a member by ip which could be either ipv4 or ip6."""
    ip_ver = get_ip_version(member_ip)
    if ip_ver == 4:
        member = find_one_in_list('member_ip', member_ip, members)
    else:
        member = find_one_in_list('member_ipv6', member_ip, members)
    return member


def get_nameservers(ib_dns_members, ip_version):
    if (not isinstance(ib_dns_members, list) or
            ip_version not in [4, 6]):
        raise ValueError("Invalid argument was passed.")

    # Prefer member_dns_ipX and fallback to member_ipX if dns one not set
    nameservers = [n for n in [m.member_dns_ipv6 or m.member_ipv6
                               if ip_version == 6
                               else m.member_dns_ip or m.member_ip
                               for m in ib_dns_members] if n]
    return nameservers


def get_mapping_relation(member_type):
    if member_type == const.MEMBER_TYPE_CP_MEMBER:
        return const.MAPPING_RELATION_DELEGATED
    if member_type == const.MEMBER_TYPE_GRID_MASTER:
        return const.MAPPING_RELATION_GM_OWNED
    return None
