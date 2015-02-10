=========================================
 Enabling Cisco Openstack SQE in Devstack
=========================================
1. Why it's needed?
   Files in this folder make this repo to be a devstack plugin, thus allowing to execute fabric facilities
   from usual devstack chain of execution. They serve as entry point to which devstack gives control in a number of phases
   during devstack's ``stack.sh`` run. See details in ``plugin.sh``.

2. How to switch it on in devstack config?
    a. Download DevStack git clone https://github.com/openstack-dev/devstack.git
    b. Add this repo as an external repository by including the following line in [[local:localrc]] section of local.conf::

     enable_plugin cisco-sqe https://github.com/cisco-openstack/openstack-sqe.git
     enable_service  cisco-sqe
     CISCO_SQE_FACILITY=<facility>


     CISCO_SQE_FACILITY defines the facility which will be invoked. If to leave this variable undefined,
     devstack will cease installation, providing you with the list of all possible facilities. That the same list is
     also provided by executing

     fab -l

     when in base folder of the repo.

    c. run ``stack.sh`` as usual
