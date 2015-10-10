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

import datetime
import decimal
import hashlib
import netaddr
import random
import re
import six
import urllib

from oslo_log import log as logging
from oslo_serialization import jsonutils

from networking_infoblox.neutron.common import constants as const


LOG = logging.getLogger(__name__)


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


def construct_ea(attributes):
    ea = {}
    for name, value in six.iteritems(attributes):
        str_val = get_string_or_none(value)
        if str_val:
            ea[name] = {'value': str_val}

    ea[const.EA_CLOUD_MGMT_PLATFORM_TYPE] = {'value': 'OpenStack'}
    return ea


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
        name_attr = root.get(name)
        if name_attr:
            value = name_attr.get('value')
            if should_return_list_value and not isinstance(value, list):
                value = [value]
    return value


def get_ip_version(ip_address):
    valid = ip_address and isinstance(ip_address, six.string_types)
    if not valid:
        raise ValueError("Invalid argument was passed")

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
        raise ValueError("Invalid argument was passed")
    duid = [0x00,
            random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff),
            random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, duid)) + ':' + mac


def get_prefix_for_dns_zone(subnet_name, cidr):
    valid = cidr and isinstance(cidr, six.string_types)
    if not valid:
        raise ValueError("Invalid argument was passed")

    subnet_name = subnet_name if subnet_name else ''
    try:
        ip_version = get_ip_version(cidr)
    except netaddr.core.AddrFormatError:
        raise ValueError("Invalid cidr")

    # add prefix only for classless networks (ipv4) mask greater than
    # 24 needs prefix; use meaningful prefix if used
    prefix = None
    if ip_version == 4:
        m = re.search(r'/\d+', cidr)
        mask = m.group().replace("/", "")
        if int(mask) > 24:
            if len(subnet_name) > 0:
                prefix = subnet_name
            else:
                prefix = '-'.join(
                    filter(None,
                           re.split(r'[.:/]', cidr))
                )
    return prefix


def get_physical_network_meta(network):
    if not isinstance(network, dict):
        raise ValueError("Invalid argument was passed")

    if not network:
        return {}

    network = network if network else {}
    provider_network_type = network.get('provider:network_type')
    provider_physical_network = network.get('provider:physical_network')
    provider_segmentation_id = network.get('provider:segmentation_id')
    network_meta = {'network_type': provider_network_type,
                    'physical_network': provider_physical_network,
                    'segmentation_id': provider_segmentation_id}
    return network_meta


def get_list_from_string(data_string, delimiter_list):
    valid = (data_string and
             isinstance(data_string, six.string_types) and
             delimiter_list and
             isinstance(delimiter_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed")

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

    raise ValueError("Unsupported delimiter list type")


def exists_in_sequence(sub_sequence_to_find, full_list_in_sequence):
    valid = (isinstance(sub_sequence_to_find, list) and
             isinstance(full_list_in_sequence, list))
    if not valid:
        raise ValueError("Invalid argument was passed")

    if not sub_sequence_to_find or not full_list_in_sequence:
        return False

    return any(full_list_in_sequence[pos:pos + len(sub_sequence_to_find)] ==
               sub_sequence_to_find for pos in
               range(0,
                     len(full_list_in_sequence) - len(sub_sequence_to_find)
                     + 1))


def exists_in_list(list_to_find, full_list):
    valid = isinstance(list_to_find, list) and isinstance(full_list, list)
    if not valid:
        raise ValueError("Invalid argument was passed")

    if not list_to_find or not full_list:
        return False

    found_list = [m for m in list_to_find if m in full_list]
    return len(found_list) == len(list_to_find)


def find_one_in_list(search_key, search_value, search_list):
    """Find one item that match searching one key and value."""
    valid = (isinstance(search_key, six.string_types) and
             isinstance(search_value, six.string_types) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed")

    if not search_key or not search_value or not search_list:
        return None

    found_list = [m for m in search_list
                  if m.get(search_key) == search_value]
    return found_list[0] if found_list else None


def find_one_in_list_by_condition(search_key_value_pairs, search_list):
    """Find one item that match given search key value pairs.

    :param search_key_value_pairs: dictionary that contains search key and
    values
    :param search_list: list of dictionary objects to search
    :return: a single item that matches criteria or None
    """
    valid = (isinstance(search_key_value_pairs, dict) and
             isinstance(search_list, list))
    if not valid:
        raise ValueError("Invalid argument was passed")

    if not search_key_value_pairs or not search_list:
        return None

    result = None
    for m in search_list:
        found_counter = 0
        for key in search_key_value_pairs:
            if m.get(key) == search_key_value_pairs[key]:
                found_counter += 1
        if found_counter > 0 and found_counter == len(search_key_value_pairs):
            result = m
            break
    return result


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
        raise ValueError("Invalid argument was passed")

    if not search_key or not search_values or not search_list:
        return None

    found_list = [m for m in search_list
                  if m.get(search_key) in search_values]
    return found_list


def merge_list(*list_args):
    merge_lsit = []
    for lst in list_args:
        if not isinstance(lst, list):
            raise ValueError("Invalid argument was passed")
        merge_lsit += lst
    return list(set(merge_lsit))


def remove_any_space(text):
    if text:
        return re.sub(r'\s+', '', text)
    return text


def get_hash(text):
    if text and isinstance(text, six.string_types):
        text = text.encode('utf-8')
        return hashlib.md5(text).hexdigest()
    return None


def get_oid_from_nios_ref(obj_ref):
    if obj_ref and len(obj_ref) > 0:
        match = re.search('\S+\/(\S+):(\S+)', obj_ref)
        if match:
            return match.group(1)
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
