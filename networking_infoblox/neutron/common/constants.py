# Copyright (c) 2015 Infoblox Inc.
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

from neutron_lib import constants as n_const
from neutron_lib.plugins import constants as p_const


CLOUD_PLATFORM_NAME = 'OpenStack'

NETVIEW_MAX_LEN = 56

AGENT_BINARY_NAME = 'infoblox-ipam-agent'
AGENT_TYPE_INFOBLOX_IPAM = 'Infoblox IPAM agent'
AGENT_TOPIC = 'infoblox_ipam_agent'
AGENT_NOTIFICATION_POOL = 'infoblox-ipam-notification'

NOTIFICATION_EXCHANGE_NEUTRON = 'neutron'
NOTIFICATION_EXCHANGE_NOVA = 'nova'

GRID_STATUS_ON = 'ON'
GRID_STATUS_OFF = 'OFF'

MEMBER_RESERVATION_RETRY = 5
MEMBER_STATUS_ON = 'ON'
MEMBER_STATUS_OFF = 'OFF'

MEMBER_NODE_STATUS_FAILED = 'FAILED'
MEMBER_NODE_STATUS_INACTIVE = 'INACTIVE'
MEMBER_NODE_STATUS_WARNING = 'WARNING'
MEMBER_NODE_STATUS_WORKING = 'WORKING'

MEMBER_TYPE_GRID_MASTER = 'GM'
MEMBER_TYPE_CP_MEMBER = 'CPM'
MEMBER_TYPE_REGULAR_MEMBER = 'REGULAR'

# Cloud Network Automation for GM
MEMBER_LICENSE_TYPE_CLOUD = 'CLOUD'
# Cloud platform for CPM
MEMBER_LICENSE_TYPE_CLOUD_API = 'CLOUD_API'

SERVICE_TYPE_DHCP = 'DHCP'
SERVICE_TYPE_DNS = 'DNS'

EA_GRID_CONFIG_GRID_SYNC_SUPPORT = 'Grid Sync Support'
EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME = 'Grid Sync Minimum Wait Time'
EA_GRID_CONFIG_GRID_SYNC_MAXIMUM_WAIT_TIME = 'Grid Sync Maximum Wait Time'
EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE = 'Default Network View Scope'
EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW = 'Default Network View'
EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN = 'Default Host Name Pattern'
EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN = 'Default Domain Name Pattern'
EA_GRID_CONFIG_EXTERNAL_HOST_NAME_PATTERN = 'External Host Name Pattern'
EA_GRID_CONFIG_EXTERNAL_DOMAIN_NAME_PATTERN = 'External Domain Name Pattern'
EA_GRID_CONFIG_NS_GROUP = 'NS Group'
EA_GRID_CONFIG_DNS_VIEW = 'DNS View'
EA_GRID_CONFIG_NETWORK_TEMPLATE = 'Network Template'
EA_GRID_CONFIG_ADMIN_NETWORK_DELETION = 'Admin Network Deletion'
EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY = 'IP Allocation Strategy'
EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES = 'DNS Record Binding Types'
EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES = 'DNS Record Unbinding Types'
EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES = 'DNS Record Removable Types'
EA_GRID_CONFIG_DHCP_SUPPORT = 'DHCP Support'
EA_GRID_CONFIG_DNS_SUPPORT = 'DNS Support'
EA_GRID_CONFIG_RELAY_SUPPORT = 'Relay Support'
EA_GRID_CONFIG_USE_GM_FOR_DHCP = 'Use Grid Master for DHCP'
EA_GRID_CONFIG_TENANT_NAME_PERSISTENCE = 'Tenant Name Persistence'
EA_GRID_CONFIG_REPORT_GRID_SYNC_TIME = 'Report Grid Sync Time'
EA_GRID_CONFIG_ALLOW_SERVICE_RESTART = 'Allow Service Restart'
EA_GRID_CONFIG_ALLOW_STATIC_ZONE_DELETION = 'Allow Static Zone Deletion'
EA_GRID_CONFIG_ZONE_CREATION_STRATEGY = 'Zone Creation Strategy'

EA_LAST_GRID_SYNC_TIME = 'Last Grid Sync Time'

EA_MAPPING_ADDRESS_SCOPE_ID = 'Address Scope ID Mapping'
EA_MAPPING_ADDRESS_SCOPE_NAME = 'Address Scope Name Mapping'
EA_MAPPING_TENANT_ID = 'Tenant ID Mapping'
EA_MAPPING_TENANT_NAME = 'Tenant Name Mapping'
EA_MAPPING_NETWORK_ID = 'Network ID Mapping'
EA_MAPPING_NETWORK_NAME = 'Network Name Mapping'
EA_MAPPING_SUBNET_ID = 'Subnet ID Mapping'
EA_MAPPING_SUBNET_CIDR = 'Subnet CIDR Mapping'

EA_CLOUD_ADAPTER_ID = 'Cloud Adapter ID'
EA_IS_CLOUD_MEMBER = 'Is Cloud Member'

EA_SUBNET_ID = 'Subnet ID'
EA_SUBNET_NAME = 'Subnet Name'
EA_NETWORK_ID = 'Network ID'
EA_NETWORK_NAME = 'Network Name'
EA_NETWORK_ENCAP = 'Network Encap'
EA_SEGMENTATION_ID = 'Segmentation ID'
EA_PHYSICAL_NETWORK_NAME = 'Physical Network Name'
EA_PORT_ID = 'Port ID'
EA_PORT_DEVICE_OWNER = 'Port Attached Device - Device Owner'
EA_PORT_DEVICE_ID = 'Port Attached Device - Device ID'
EA_VM_ID = 'VM ID'
EA_VM_NAME = 'VM Name'
EA_IP_TYPE = 'IP Type'
EA_TENANT_ID = 'Tenant ID'
EA_TENANT_NAME = 'Tenant Name'
EA_ACCOUNT = 'Account'
EA_CLOUD_API_OWNED = 'Cloud API Owned'
EA_CMP_TYPE = 'CMP Type'
EA_IS_EXTERNAL = 'Is External'
EA_IS_SHARED = 'Is Shared'

REQUIRED_EA_LIST = [EA_CMP_TYPE, EA_TENANT_ID, EA_CLOUD_API_OWNED]

NETWORK_EA_LIST = [EA_ACCOUNT, EA_TENANT_NAME,
                   EA_IS_EXTERNAL, EA_IS_SHARED, EA_SUBNET_ID, EA_SUBNET_NAME,
                   EA_NETWORK_ID, EA_NETWORK_NAME, EA_NETWORK_ENCAP,
                   EA_SEGMENTATION_ID, EA_PHYSICAL_NETWORK_NAME]

RANGE_EA_LIST = [EA_ACCOUNT, EA_TENANT_NAME]

ZONE_EA_LIST = [EA_ACCOUNT, EA_TENANT_NAME]

IP_TYPE_FIXED = 'Fixed'
IP_TYPE_FLOATING = 'Floating'
IP_TYPE_PUBLIC = 'Public'
IP_TYPE_PRIVATE = 'Private'
IP_TYPE_ELASTIC = 'Elastic'

IP_ALLOCATION_STRATEGY_HOST_RECORD = 'Host Record'
IP_ALLOCATION_STRATEGY_FIXED_ADDRESS = 'Fixed Address'

DNS_RECORD_TYPE_A = 'record:a'
DNS_RECORD_TYPE_AAAA = 'record:aaaa'
DNS_RECORD_TYPE_PTR = 'record:ptr'
DNS_RECORD_TYPE_TXT = 'record:txt'

NETWORK_VIEW_SCOPE_SINGLE = 'Single'
NETWORK_VIEW_SCOPE_ADDRESS_SCOPE = 'Address Scope'
NETWORK_VIEW_SCOPE_TENANT = 'Tenant'
NETWORK_VIEW_SCOPE_NETWORK = 'Network'
NETWORK_VIEW_SCOPE_SUBNET = 'Subnet'

MAPPING_CONDITION_KEY_NAME = 'neutron_object_name'
MAPPING_CONDITION_VALUE_NAME = 'neutron_object_value'

MAPPING_RELATION_GM_OWNED = 'GM-OWNED'
MAPPING_RELATION_DELEGATED = 'DELEGATED'

DEFAULT_NETWORK_VIEW = 'default'
DEFAULT_DNS_VIEW = 'default'

IS_DEFAULT = 'is_default'

NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP = {
    n_const.DEVICE_OWNER_DHCP: 'dhcp-port-{ip_address}',
    n_const.DEVICE_OWNER_ROUTER_INTF: 'router-iface-{ip_address}',
    n_const.DEVICE_OWNER_ROUTER_GW: 'router-gw-{ip_address}',
    n_const.DEVICE_OWNER_FLOATINGIP: 'floating-ip-{ip_address}',
    'neutron:' + p_const.LOADBALANCER: 'lb-vip-{ip_address}'
}

NEUTRON_INTERNAL_SERVICE_DEVICE_OWNERS = [
    n_const.DEVICE_OWNER_DHCP,
    n_const.DEVICE_OWNER_ROUTER_INTF,
    n_const.DEVICE_OWNER_ROUTER_GW,
    'neutron:' + p_const.LOADBALANCER
]

NEUTRON_DEVICE_OWNER_COMPUTE_NOVA = 'compute:nova'
# nova has a bug that it returns compute:None when an instance is created from
# CLI command: nova-boot.
NEUTRON_DEVICE_OWNER_COMPUTE_NONE = 'compute:None'
NEUTRON_DEVICE_OWNER_COMPUTE_LIST = [NEUTRON_DEVICE_OWNER_COMPUTE_NOVA,
                                     NEUTRON_DEVICE_OWNER_COMPUTE_NONE]

NEUTRON_FLOATING_IP_DEVICE_OWNERS = [
    n_const.DEVICE_OWNER_FLOATINGIP,
    NEUTRON_DEVICE_OWNER_COMPUTE_NOVA,
    NEUTRON_DEVICE_OWNER_COMPUTE_NONE
]

NONE_ID = 'NONE'
EA_RESET_VALUE = 'N/A'

ZONE_CREATION_STRATEGY_FORWARD = 'Forward'
ZONE_CREATION_STRATEGY_REVERSE = 'Reverse'

REQUIRED_EA_DEFS = [
    # Cloud Property EAs
    {'name': EA_ACCOUNT, 'type': 'STRING', 'flags': 'C',
     'comment': 'User ID in OpenStack'},

    {'name': EA_CLOUD_API_OWNED, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'Is Cloud API owned'},

    {'name': EA_CMP_TYPE, 'type': 'STRING', 'flags': 'C',
     'comment': 'CMP Types (OpenStack)'},

    {'name': EA_IS_EXTERNAL, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': EA_IS_SHARED, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': EA_IP_TYPE, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': IP_TYPE_ELASTIC},
                     {'value': IP_TYPE_FIXED},
                     {'value': IP_TYPE_FLOATING},
                     {'value': IP_TYPE_PRIVATE},
                     {'value': IP_TYPE_PUBLIC}],
     'comment': 'Type of IP address'},

    {'name': EA_NETWORK_ENCAP, 'type': 'STRING', 'flags': 'C',
     'comment': 'Type of IP address'},

    {'name': EA_NETWORK_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Network ID in OpenStack'},

    {'name': EA_NETWORK_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Network Name'},

    {'name': EA_PHYSICAL_NETWORK_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': EA_PORT_DEVICE_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': EA_PORT_DEVICE_OWNER, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': EA_PORT_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': EA_SEGMENTATION_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': EA_SUBNET_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Subnet ID in OpenStack'},

    {'name': EA_SUBNET_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Subnet Name in OpenStack'},

    {'name': EA_TENANT_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Tenant ID in OpenStack'},

    {'name': EA_TENANT_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Tenant Name in OpenStack'},

    {'name': EA_VM_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Instance ID in OpenStack'},

    {'name': EA_VM_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Instance Name in OpenStack'},

    # Grid Configuration EAs
    {'name': EA_GRID_CONFIG_GRID_SYNC_SUPPORT,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME,
     'type': 'INTEGER', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_GRID_SYNC_MAXIMUM_WAIT_TIME,
     'type': 'INTEGER', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': NETWORK_VIEW_SCOPE_SINGLE},
                     {'value': NETWORK_VIEW_SCOPE_ADDRESS_SCOPE},
                     {'value': NETWORK_VIEW_SCOPE_TENANT},
                     {'value': NETWORK_VIEW_SCOPE_NETWORK},
                     {'value': NETWORK_VIEW_SCOPE_SUBNET}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_EXTERNAL_HOST_NAME_PATTERN,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_EXTERNAL_DOMAIN_NAME_PATTERN,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_NS_GROUP,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DNS_VIEW,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_NETWORK_TEMPLATE,
     'type': 'STRING', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': IP_ALLOCATION_STRATEGY_HOST_RECORD},
                     {'value': IP_ALLOCATION_STRATEGY_FIXED_ADDRESS}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DHCP_SUPPORT,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_DNS_SUPPORT,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_RELAY_SUPPORT,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_USE_GM_FOR_DHCP,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_TENANT_NAME_PERSISTENCE,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_REPORT_GRID_SYNC_TIME,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_ALLOW_SERVICE_RESTART,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_ALLOW_STATIC_ZONE_DELETION,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Configuration'},

    {'name': EA_GRID_CONFIG_ZONE_CREATION_STRATEGY,
     'type': 'ENUM', 'flags': 'CGV',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': ZONE_CREATION_STRATEGY_FORWARD},
                     {'value': ZONE_CREATION_STRATEGY_REVERSE}],
     'comment': 'Grid Configuration'},

    # Grid Report
    {'name': EA_LAST_GRID_SYNC_TIME,
     'type': 'STRING', 'flags': 'CV',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Sync Report'},

    # Mapping EAs
    {'name': EA_MAPPING_ADDRESS_SCOPE_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_ADDRESS_SCOPE_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_TENANT_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_TENANT_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_NETWORK_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_NETWORK_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_SUBNET_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': EA_MAPPING_SUBNET_CIDR,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    # Cloud Participation EA
    {'name': EA_CLOUD_ADAPTER_ID,
     'type': 'STRING', 'flags': 'CV',
     'comment': 'Cloud Participation'},

    # Member Registration EA
    {'name': EA_IS_CLOUD_MEMBER,
     'type': 'ENUM', 'flags': 'CG',
     'allowed_object_types': ['Member'],
     'list_values': [{'value': 'True'},
                     {'value': 'False'}],
     'comment': 'Grid Membership'}
]

# names of EAs which can contains multiple values
EA_MULTI_VALUES = [ea_def['name'] for ea_def in REQUIRED_EA_DEFS
                   if 'V' in ea_def['flags']]


GRID_CONFIG_DEFAULTS = {
    EA_GRID_CONFIG_GRID_SYNC_SUPPORT: True,
    EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME: 60,
    EA_GRID_CONFIG_GRID_SYNC_MAXIMUM_WAIT_TIME: 300,
    EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE: NETWORK_VIEW_SCOPE_SINGLE,
    EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW: DEFAULT_NETWORK_VIEW,
    EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN: 'host-{ip_address}',
    EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN: '{subnet_id}.cloud.global.com',
    EA_GRID_CONFIG_EXTERNAL_HOST_NAME_PATTERN: '{instance_name}',
    EA_GRID_CONFIG_EXTERNAL_DOMAIN_NAME_PATTERN:
        '{subnet_id}.external.global.com',
    EA_GRID_CONFIG_NS_GROUP: None,
    EA_GRID_CONFIG_DNS_VIEW: DEFAULT_DNS_VIEW,
    EA_GRID_CONFIG_NETWORK_TEMPLATE: None,
    EA_GRID_CONFIG_ADMIN_NETWORK_DELETION: False,
    EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY: (
        IP_ALLOCATION_STRATEGY_FIXED_ADDRESS),
    EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES: [DNS_RECORD_TYPE_A,
                                              DNS_RECORD_TYPE_AAAA,
                                              DNS_RECORD_TYPE_PTR],
    EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES: [DNS_RECORD_TYPE_A,
                                                DNS_RECORD_TYPE_AAAA,
                                                DNS_RECORD_TYPE_PTR],
    EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES: [DNS_RECORD_TYPE_A,
                                                DNS_RECORD_TYPE_AAAA,
                                                DNS_RECORD_TYPE_PTR,
                                                DNS_RECORD_TYPE_TXT],
    EA_GRID_CONFIG_DHCP_SUPPORT: False,
    EA_GRID_CONFIG_DNS_SUPPORT: False,
    EA_GRID_CONFIG_RELAY_SUPPORT: False,
    EA_GRID_CONFIG_USE_GM_FOR_DHCP: True,
    EA_GRID_CONFIG_TENANT_NAME_PERSISTENCE: False,
    EA_GRID_CONFIG_REPORT_GRID_SYNC_TIME: False,
    EA_GRID_CONFIG_ALLOW_SERVICE_RESTART: True,
    EA_GRID_CONFIG_ALLOW_STATIC_ZONE_DELETION: False,
    EA_GRID_CONFIG_ZONE_CREATION_STRATEGY: [ZONE_CREATION_STRATEGY_FORWARD,
                                            ZONE_CREATION_STRATEGY_REVERSE],
    EA_LAST_GRID_SYNC_TIME: None
}

FEATURE_VERSIONS = {
    'create_ea_def': '2.2',
    'cloud_api': '2.0',
    'member_ipv6_setting': '2.2',
    'member_licenses': '2.0',
    'enable_member_dns': '2.2.1',
    'enable_member_dhcp': '2.2.1',
    'dns_settings': '2.3',
    'enable_dhcp': '2.2.1',
    'tenants': '2.0',
}
