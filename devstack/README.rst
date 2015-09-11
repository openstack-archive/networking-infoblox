Enabling in Devstack
====================

1. Download DevStack

2. Add this repo as an external repository:

    > cat local.conf
    [[local|localrc]]
    enable_service networking-infoblox https://github.com/openstack/networking-infoblox

3. run stack.sh