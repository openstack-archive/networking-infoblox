Release Notes
-------------

10.0.1 (2018-03-05)
__________________

Enhancements
~~~~~~~~~~~~
* Support CP Member
    - Support for grid_sync when GM is disconnected
    - Added force_proxy=True for member_object
    - Added 'CG' flags in GRID_CONFIGURATION EA's
* Support for pagination
* Optimized mapping sync flow.
* Added filter of CMP Type on GET network


Fixes
~~~~~
* Fixed issue of stale entry for dhcp ip if ip allocation strategy is fixed address.
* Fixed issue where IPAllocation fails and log trace not show reason of failure.
* Removed OS_REGION_NAME dependency from sync tools.
* Fixed issue where NIOS password was visible in infoblox plugin & agent logs.
* Fixed exceptions when uppercase name used for creating resources in openstack
* Fixed exception handling for case of conflict while creation of the ip object.
