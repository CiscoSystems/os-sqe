from fabric.api import task, local, env
from common import timed
from common import logger as log
from fabs import LAB, DEFAULT_SETTINGS

__all__ = ["create", "restore", "destroy", "shutdown"]

env.update(DEFAULT_SETTINGS)
LAB_ID = LAB + "-"


@task
@timed
def create():
    ''' Create snapshots for all VMs for current lab and shutdown them all '''
    log.info("Creating snapshots for lab %s" % LAB)
    vms = local("virsh list --name | grep '%s'" % LAB_ID, capture=True)
    for vm in vms.stdout.splitlines():
        local("virsh snapshot-create-as {vm_name} original".format(vm_name=vm))
        log.info('VM %s was snapshotted' % vm)
        local("virsh shutdown {vm_name}".format(vm_name=vm))
        log.info('VM %s was shut down' % vm)


@task
@timed
def restore():
    ''' Restore all snapshotted VMs from current lab '''
    log.info('Restoring snapshots for lab %s' % LAB)
    vms = local("virsh list --name --all | grep '%s'" % LAB_ID, capture=True)
    for vm in vms.stdout.splitlines():
        local("virsh snapshot-revert {vm} original".format(vm=vm))
        log.info('VM %s was reverted to original snapshot' % vm)
    for comp in ('pool', 'net'):
        comp_raw = local("virsh {comp}-list --all | grep '{lab_id}'".format(
            comp=comp, lab_id=LAB_ID), capture=True)
        comps = comp_raw.stdout.splitlines()
        comps_dict = dict(((i.split()[0], i.split()[1:]) for i in comps))
        for k, v in comps_dict.iteritems():
            if v[0] == "inactive":
                local("virsh {comp}-start {name}".format(comp=comp, name=k))


@task
@timed
def destroy():
    ''' Shutdown VMs and delete all snapshots from current lab '''
    log.info('Destroying VMs and snapshots for lab %s' % LAB)
    vms = local("virsh list --name --all | grep '%s'" % LAB_ID, capture=True)
    for vm in vms.stdout.splitlines():
        snaps = local("virsh snapshot-list %s --name" % vm, capture=True)
        for snap in snaps.stdout.splitlines():
            local("virsh snapshot-delete {vm} {snap}".format(vm=vm, snap=snap))
            log.info("Snapshot '{snap}' from VM {vm} was deleted".format(snap=snap, vm=vm))

@task
@timed
def shutdown():
    ''' Just shutdown VMs from current lab '''
    log.info("Shutting down VMs for lab %s" % LAB)
    vms = local("virsh list --name | grep '%s'" % LAB_ID, capture=True)
    for vm in vms.stdout.splitlines():
        local("virsh shutdown {vm_name}".format(vm_name=vm))
        log.info('VM %s was shut down' % vm)
