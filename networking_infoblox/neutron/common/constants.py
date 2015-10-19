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

AGENT_BINARY_NAME = 'infoblox-ipam-agent'
AGENT_TYPE_INFOBLOX_IPAM = 'Infoblox IPAM agent'
AGENT_TOPIC = 'infoblox_ipam_agent'

GRID_STATUS_ON = 'ON'
GRID_STATUS_OFF = 'OFF'

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

EA_CLOUD_MGMT_PLATFORM_TYPE = 'CMP Type'
EA_GRID_CONFIG_GRID_SYNC_SUPPORT = 'Grid Sync Support'
EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME = 'Grid Sync Minimum Wait Time'
EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE = 'Default Network View Scope'
EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW = 'Default Network View'
EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN = 'Default Host Name Pattern'
EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN = 'Default Domain Name Pattern'
EA_GRID_CONFIG_NS_GROUP = 'NS Group'
EA_GRID_CONFIG_NETWORK_TEMPLATE = 'Network Template'
EA_GRID_CONFIG_ADMIN_NETWORK_DELETION = 'Admin Network Deletion'
EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY = 'IP Allocation Strategy'
EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES = 'DNS Record Binding Types'
EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES = 'DNS Record Unbinding Types'
EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES = 'DNS Record Removable Types'
EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK_VIEW = \
    'DHCP Relay Management Network View'
EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK = 'DHCP Relay Management Network'
EA_GRID_CONFIG_DHCP_SUPPORT = 'DHCP Support'
EA_MAPPING_ADDRESS_SCOPE_ID = 'Address Scope ID Mapping'
EA_MAPPING_ADDRESS_SCOPE_NAME = 'Address Scope Name Mapping'
EA_MAPPING_TENANT_ID = 'Tenant ID Mapping'
EA_MAPPING_TENANT_NAME = 'Tenant Name Mapping'
EA_MAPPING_TENANT_CIDR = 'Tenant CIDR Mapping'
EA_MAPPING_NETWORK_ID = 'Network ID Mapping'
EA_MAPPING_NETWORK_NAME = 'Network Name Mapping'
EA_MAPPING_SUBNET_ID = 'Subnet ID Mapping'
EA_MAPPING_SUBNET_CIDR = 'Subnet CIDR Mapping'

IP_ALLOCATION_STRATEGY_HOST_RECORD = 'Host Record'
IP_ALLOCATION_STRATEGY_FIXED_ADDRESS = 'Fixed Address'

NETWORK_VIEW_SCOPE_SINGLE = 'Single'
NETWORK_VIEW_SCOPE_ADDRESS_SCOPE = 'Address Scope'
NETWORK_VIEW_SCOPE_TENANT = 'Tenant'
NETWORK_VIEW_SCOPE_NETWORK = 'Network'
NETWORK_VIEW_SCOPE_SUBNET = 'Subnet'

MAPPING_CONDITION_KEY_NAME = 'neutron_object_name'
MAPPING_CONDITION_VALUE_NAME = 'neutron_object_value'

MAPPING_RELATION_GM_OWNED = 'GM-OWNED'
MAPPING_RELATION_DELEGATED = 'DELEGATED'
