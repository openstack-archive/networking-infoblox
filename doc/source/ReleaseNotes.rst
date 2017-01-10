Release Notes
-------------

9.0.0 (2017-01-13)
__________________

Enhancements
~~~~~~~~~~~~
* Implement IPAM-DHCP only scenario
* Additional EAs for zones
* Zone create on netrwork name update
* Fix IP allocator to reuse IP with same MAC
* Keystone v3 support in syn_neutron_to_infoblox

Fixes
~~~~~
* Remove use of neutron_lib.plugins for Newton
* Use model_base (and other things) from neutron-lib
* Use member_ip to query for Grid Master
* Delete DNS Name Server option if empty
* Fix empty DNS Name Server option
* Update installation doc
* Update infoblox-client requirement
* Use model_base (and other things) from neutron-lib (Newton Only)
* Fix README
* Changed the home-page link
* Don't include openstack/common in flake8 exclude list
* Drop MANIFEST.in - it's not needed by pbr
* Update .coveragerc after the removal of openstack directory
* Fix documentation link
* TrivialFix: Remove logging import unused
* Update Installation documentation
* Use independent session for grid sync
* Enable DeprecationWarning in test environments

