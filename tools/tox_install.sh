#!/bin/sh

# Many of neutron's repos suffer from the problem of depending on neutron,
# but it not existing on pypi.

# This wrapper for tox's package installer will use the existing package
# if it exists, else use zuul-cloner if that program exists, else grab it
# from neutron master via a hard-coded URL. That last case should only
# happen with devs running unit tests locally.

# From the tox.ini config page:
# install_command=ARGV
# default:
# pip install {opts} {packages}

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner
UPPER_CONSTRAINTS_FILE=${UPPER_CONSTRAINTS_FILE:-unconstrained}
neutron_installed=$(echo "import neutron" | python 2>/dev/null ; echo $?)
install_cmd="pip install"

if [ "$UPPER_CONSTRAINTS_FILE" != "unconstrained" ]; then
    install_cmd="$install_cmd -c$UPPER_CONSTRAINTS_FILE"
fi

set -ex

cwd=$(/bin/pwd)

if [ $neutron_installed -eq 0 ]; then
    echo "ALREADY INSTALLED" > /tmp/tox_install.txt
    echo "Neutron already installed; using existing package"
elif [ -x "$ZUUL_CLONER" ]; then
    echo "ZUUL CLONER" > /tmp/tox_install.txt
    cd /tmp
    $ZUUL_CLONER --cache-dir \
        /opt/git \
        --branch master \
        git://git.openstack.org \
        openstack/neutron
    cd openstack/neutron
    git checkout $BRANCH_NAME
    $install_cmd -e .
    cd "$cwd"
else
    echo "PIP HARDCODE" > /tmp/tox_install.txt
    $install_cmd -U -egit+https://git.openstack.org/openstack/neutron@$BRANCH_NAME#egg=neutron
    $install_cmd -U -e $VIRTUAL_ENV/src/neutron
fi

$install_cmd -U $*
exit $?
