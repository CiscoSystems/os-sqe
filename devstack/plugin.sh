#!/bin/sh
# stack.sh calls this script in phases with following arguments:
# phase 1 stack pre-install
# phase 2 stack install
# phase 3 stack post-config
# phase 4 stack extra
# unstack.sh calls this script with following arguments
# phase 1 unstack

function sqe_pre_install
{
    :
}

function sqe_install
{
    fab -f ${dir}/fabfile.py ${CISCO_SQE_FACILITY} # $dir points to newly cloned plugin repo
}

function sqe_post_config
{
    :
}

function sqe_extra
{
    :
}

function sqe_unstack
{
    fab -f ${dir}/fabfile.py ${CISCO_SQE_FACILITY}:cleanup # $dir points to newly cloned plugin repo
}

if is_service_enabled cisco-sqe; then
    case $1 in
        stack)
            case $2 in
                pre-install) sqe_pre_install ;;
                install) sqe_install ;;
                post-config) sqe_post_config ;;
                extra) sqe_extra ;;
            esac ;;
        unstack) sqe_unstack ;;
    esac
fi
