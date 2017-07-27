============================
Infoblox Configuration Guide
============================

The Installation guide provides the configuration options for Neutron and Nova,
as well as the most common Infoblox configuration options. However, there are
some additional options available when configuring the Infoblox side of the
integration. This guide will provide details on each available option. It will
repeat the options described in the Installation section for completeness.

As discussed in the Installation guide, these should be set on the grid
master (GM) member object. It is also possible to pre-define mappings for
individual OpenStack entities; those EAs will be set on the specific network
view in Infoblox. This is discussed in more detail below.

Grid Synchronization Settings
-----------------------------
When you make a change to the EAs in Infoblox that represent the driver
configuration, that change must be synchronized to the driver's local
storage. Set on the grid master object, the following EAs define grid
synchronization settings:

`Grid Sync Support`. This EA is used to choose whether to enable
synchronization of grid configuration from Infoblox. The default is True.

`Grid Sync Minimum Wait Time`. This EA is used to define the minimum wait time,
in seconds, before a synchronization is allowed to take place. The default is
60.

`Grid Sync Maximum Wait Time`. This EA is used to define the maximum wait time,
in seconds, between synchronizations. The default is 300.

`Report Grid Sync Time` This EA is used to allow reporting of grid sync time.
The default is False. If this is set to True, `Last Grid Sync Time` EA is used
to store last grid sync time. The infoblox-ipam-agent updates grid sync time.
It is important to note that setting this EA to True requires a WRITE
permission on the grid member.

Network View Mapping
--------------------
When creating a new object in Infoblox, the IPAM driver must know the network
view in which to create the object. This is determined using a number of EAs.

In the simpliest form you can configure the driver to automatically create
network views as needed. The first EA that needs to be set is the
`Default Network View Scope`. This EA defines the default mapping to network
view when no mapping already exists within the Infoblox system. This can be
any of the following values:

1) ``Single``. This means that any time a pre-existing mapping cannot be found,
   the resulting object should be placed within a single, specific network
   view. That view should be specified with another EA, `Default Network View`.

2) ``Tenant``. This means that any time a pre-existing mapping cannot be found,
   the resulting object should be placed within a network view determined by
   the OpenStack tenant that owns the object. If no network view tagged with
   that Tenant ID exists, then a new network view will be created with the name
   ``tenant_name``.``tenant_id``.

3) ``Address Scope``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack address scope associated with the object.
   Address scopes are not fully supported in OpenStack Liberty, and so this
   value should not be used until a later version of the driver is available
   supporting this Mitaka feature.

4) ``Network``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack network. This is rarely used and primarily is
   provided for use in automated testing, where the same tenant may create
   multiple OpenStack Network entities with overlapping subnets.

5) ``Subnet``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack subnet. This is rarely used, but can be
   necessary in certain deployments that utilize SDN plugins that allow
   spanning subnets across OpenStack Neutron installations.

Alternatively, You can pre-define mappings by creating a network view and then
tagging it with the name of a tenant, address scope, or network, in addition to
CIDR of a subnet. This can be done by creating the following EAs on a network
view object. Each of these EAs allows multiple values to be specified.

`Subnet CIDR Mapping` - If a subnet created matches one of the CIDR values
specified in this EA, the subnet will be created under this network view.

`Subnet ID Mapping` - If the ID of a subnet created matches one of the values
specified in this EA, the subnet will be created under this network view.

`Network Name Mapping` - If the name of a network matches one of the values
specified in this EA, the subnets within the network will be created under this
network view.

`Network ID Mapping` - If the ID of a network matches one of the values
specified in this EA, the subnets within the network will be created under this
network view.

`Tenant Name Mapping` - If the name of a tenant matches one of the values
specified in this EA, objects within the tenant will be created under this
network view.

`Tenant ID Mapping` - If the ID of a tenant matches one of the values specified
in this EA, objects within the tenant will be created under this network view.

`Address Scope Name Mapping` - If the name of an address scope matches one of
the values specified in this EA, objects within the address scope will be
created under this network view.

`Address Scope ID Mapping` - If the ID of an address scope matches one of the
values specified in this EA, objects within the address scope will be created
under this network view.

Domain and Host Name Patterns
-----------------------------

`Default Domain Name Pattern`. This EA is used to control how domain names for
IP address allocations are determined. Typically this pattern is used for
private networks (not external), but if `External Domain Name Pattern` is not
set, it applies to all network types. This EA can be set to a fixed string,
or can use patterns to generate unique zone names. For example, you may set
this to ``cloud.example.com`` to have all DNS entries within that domain. Or,
you can use substitution patterns: ``{tenant_name}.cloud.example.com`` would
place IPs associated with each tenant in their own domain.

For domain names, the following patterns are supported:

``{network_name}`` will be replaced with the OpenStack Network Name.

``{network_id}`` will be replaced with the OpenStack Network ID.

``{tenant_name}`` will be replaced with the OpenStack Tenant Name. Note that
for this to work, the `Tenant Name Persistence` EA must be set to True.

``{tenant_id}`` will be replaced with the OpenStack Tenant ID.

``{subnet_name}`` will be replaced with the OpenStack Subnet Name.

``{subnet_id}`` will be replaced with the OpenStack Subnet ID.

The DNS zones are created under a DNS View, the name of which is constructed
using the `DNS View` EA.

`External Domain Name Pattern`. This EA is used to control how domain names for
IP address allocations are determined for external networks. If this EA is
not set, then `Default Domain Name Pattern` is used for external networks.
The same patterns are supported as for `Default Domain Name Pattern`.

`Default Host Name Pattern`. This EA controls host names in a manner similar to
the way `Default Domain Name Pattern` controls domain names. In addition to the
patterns supported for domain names, this EA supports these:

``{port_id}``. The port ID of the port associated with the IP.

``{instance_id}``. The Nova instance ID of the VM associated with the port.

``{instance_name}``. The Nova instance name of the VM associated with the port.

``{ip_address}``. The IP address for this port or host, with dots replaced by
dashes.

``{ip_address_octet{n}}`` where n is a number 0-3. This is for IPv4 addresses
only. For example, if the pattern is
``host-{ip_address_octet{2}}-{ip_address_octet{3}}``
and the IP is 10.1.2.3, then the resulting hostname will be ``host-2-3``.

.. note::
  If the host name pattern is set to {instance_name}.constant_string, then
  you should not create two instances with the same name in Openstack as
  the driver will create the same DNS host record for both instances.

`External Host Name Pattern`. This EA controls host names in the same way
as `Default Host Name Pattern`, but applies only to hosts allocated
in external network. If `External Host Name Pattern` is not set,
`Default Host Name Pattern` is used for external networks.

.. note::
  Per NIOS restriction, the domain label must not be longer than 63 characters.
  For more details on prefered name syntax check: https://tools.ietf.org/html/rfc1035 [Section 2.3.1]

`Tenant Name Persistence`. Since Neutron does not have direct access to tenant
names (they are part of Keystone), the Infoblox IPAM agent can cache those
names it receives from the message bus. This reduces the Keystone API calls
needed to retrieve tenant name. This EA controls this behavior; it must be
set to True for tenant name support in domain or host names.

IPAM and DHCP/DNS Support
-------------------------

IPAM and DHCP/DNS Support can be configured by tuning `DHCP Support` and
`DNS Support` EAs.

`DHCP Support`. When set to False, DHCP support by Infoblox will be disabled
irrespective of the "Enable DHCP" option when a subnet is created in OpenStack.
The dnsmasq-based DHCP can be used instead. The default is False.

`DNS Support`. When set to False, DNS support will be disabled. Enabling it
allows DNS record generation and DNS protocol. The default is False.

Currently the following configurations are supported.

IPAM Only

 * `DHCP Support` = False
 * `DNS Support` = False

Full DHCP/DNS Support

 * `DHCP Support` = True
 * `DNS Support` = True

Creating multiple network views with specific Default Network View Scope EA:
 * `DHCP Support` = False/True
 * `DNS Support` = True

If the `DHCP Support` EA is False:

 * When the Default Network View Scope EA is set to `Single`, the Grid Master or Grid member will not be assigned to the
   network, and multiple networks will be created in the default or custom network view.
 * When the Default Network View Scope is set to `Tenant`/`Network`/`Subnet`/`Address Scope`, the Grid Master or
   Grid member will not be assigned to the network, and a network view will be added in NIOS for each new network.

If the `DHCP Support` EA is True:

 * When the Default Network View Scope is set to `Single`, the Grid Master will be assigned to multiple networks in the default
   or custom network view.
 * When the Grid is standalone and the Default Network View Scope is set to `Tenant`/`Network`/`Subnet`, we can add
   only one network with the member assigned.
 * When the Grid is standalone with a member and the Default Network View Scope is set to
   `Tenant`/`Network`/`Subnet`, we can add only two networks: one to the Grid Master and another to the Grid member.

IP Allocation and DNS Record Creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`IP Allocation Strategy`. This EA is used to choose between Host Record and
Fixed Address for IP allocation. If chosen for Fixed Address, DNS records
associated with a fixed address are controlled by the additional EAs below.

`DNS Record Binding Types`. List of DNS records to generate and bind to a
fixed address during IP allocation. Supported DNS record types are
``record:a`` (for A records), ``record:aaaa`` (for AAAA records), and
``record:ptr`` (for PTR records). This is a multi-value EA, with one of these
entries per value.

`DNS Record Unbinding Types`. List of DNS records to unbind from a
fixed address during IP deallocation. Supported DNS record types are the same
as `DNS Record Binding Types`.

`DNS Record Removable Types`. List of associated DNS records to delete when a
fixed address is deleted. This is typically a list of DNS records created
independently of the Infoblox IPAM Driver. Supported DNS record types are
``record:a``, ``record:aaaa``, ``record:ptr``, ``record:txt``, and
``record:cname``.

.. note::

  A DHCP port ip is an exception to this. The DHCP port ip is created as a host
  record with DHCP disabled to allow IP aliasing, regardless of `IP Allocation
  Strategy` configuration. IP aliasing is used in OpenStack when multiple
  subnets are created in the same network. Each subnet requires a DHCP port ip
  and those ips are all assigned to the same DHCP port, but only one MAC
  address exists. If IPAM only support configuration is used, DNS is disabled
  as well for the host record.

Identifying Members to Use
-----------------------
In order to serve DHCP and DNS, you must pick grid members to be registered to
Neutron. You should exclude network discovery members and reporting members
since they cannot serve DHCP and DNS. For the members to serve DHCP and DNS,
the licenses must be properly installed and services must be properly running.

In general in order to utilize Infoblox for DHCP, you will need to use an SDN
solution that provides a DHCP relay function. The standard Neutron functions do
not provide relay.

To identify a grid member as available for use by OpenStack, you must set the
EA `Is Cloud Member` to True. If you are running a grid but the GM is not
configured and licensed for DNS or DHCP, set `Use Grid Master for DHCP`
EA on the GM object to False. This will exclude the GM from being selected
to serve DHCP or DNS.

Miscellaneous Grid Configurations
---------------------------------
`NS Group`. Name of the  Name Server Group that will be used for serving DNS
for all DNS zones. The default is None, in which case, DNS service members will
be selected based on mapping conditions.

`Network Template`. Name of the Template to use when a network is created.
A Template contains predefined network settings. The default is None.

`Admin Network Deletion`. Specifies whether to delete object from Infoblox
when an Admin Network is deleted from OpenStack. A network that is specified
as "external" and/or "shared" is considered an Admin Network. The default is
False.

`Relay Support`. Specifies whether a Relay will be used. If set to False, then
DNS Servers option will be set to the DNS Member that IPAM driver assigns.
If True, DNS Servers option will be to the same ip as DHCP Port for the subnet.
However, if the user specifies Nameservers option when the OpenStack subnet is
created, then only the user provided nameservers would be used for DNS Servers
option, irrespective of the `Relay Support` flag.
