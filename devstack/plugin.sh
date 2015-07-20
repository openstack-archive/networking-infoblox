# plugin.sh - DevStack plugin.sh dispatch script networking_infoblox

function install_networking_infoblox {
    echo
}

function init_networking_infoblox {
    echo
}

function configure_networking_infoblox {
    echo
}

# check for service enabled
if is_service_enabled networking-infoblox; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "Configuring system services for Infoblox Networking"
        #install_package cowsay

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing Infoblox Networking"
        install_networking_infoblox

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring Infoblox Networking"
        configure_networking_infoblox

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the networking-infoblox service
        echo_summary "Initializing Infoblox Networking"
        init_networking_infoblox
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down networking_infoblox services
        # no-op
        :
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi
