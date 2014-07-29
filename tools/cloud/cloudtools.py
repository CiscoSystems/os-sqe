import os
import sys
import logging
import libvirt
import subprocess
from config import opts

from libvirt import libvirtError

LIBVIRT_URL = 'qemu+ssh://{user}@{host}/system'.format(user=opts.user, host=opts.host)

__author__ = 'sshnaidm'

def handler(ctxt, err):
    global errno
    errno = err
libvirt.registerErrorHandler(handler, 'context')

conn = libvirt.open(LIBVIRT_URL)

def run_cmd(cmd):
    """
        Return the exit status and output to stdout and stderr.
    """
    logging.debug("Running command: %s" % " ".join(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            close_fds=True)
    ret = proc.wait()
    print >> sys.stderr, "\n".join(proc.stdout.readlines()), "\n".join(proc.stderr.readlines())
    return ret, proc.stdout.readlines(), proc.stderr.readlines()

def basic(name):
    return name + "-"

def erase_net(lab):
    names = [i.name() for i in conn.listAllNetworks() if basic(lab) in i.name()]
    for net_name in names:
        try:
            net = conn.networkLookupByName(net_name)
        except libvirtError:
            print >> sys.stderr, "Network %s wasn't found, nothing to delete" % net_name
        try:
            net.destroy()
        except libvirtError:
            print >> sys.stderr, "Network %s wasn't active, undefining..." % net_name
        net.undefine()
        print >> sys.stderr, "Network %s was deleted" % net_name

def erase_pool(lab):
    names = [i.name() for i in conn.listAllStoragePools() if lab + "-default" in i.name()]
    for name in names:
        try:
            pool = conn.storagePoolLookupByName(name)
        except libvirtError:
            print >> sys.stderr, "Pool not found, nothing to delete"
            return
        try:
            pool.destroy()
        except libvirtError:
            print >> sys.stderr, "Pool wans't active, undefining..."
        pool.undefine()
        print >> sys.stderr, "Pool %s was deleted" % (lab + "-default")

def erase_vm(lab):
    names = [i.name() for i in conn.listAllDomains() if basic(lab) in i.name()]
    for name in names:
        try:
            vm = conn.lookupByName(name)
        except libvirtError:
            print >> sys.stderr, "Domain {name} not found, nothing to delete".format(name=name)
            return
        try:
            vm.destroy()
        except libvirtError:
            print >> sys.stderr, "Domain wans't active, undefining..."
        vm.undefine()
        print >> sys.stderr, "Domain {name} deleted".format(name=name)

def shutdown_vm(lab):
    names = [i.name() for i in conn.listAllDomains() if basic(lab) in i.name()]
    for name in names:
        try:
            vm = conn.lookupByName(name)
        except libvirtError:
            print >> sys.stderr, "Domain {name} not found, nothing to shutdown".format(name=name)
            return
        try:
            vm.shutdown()
            print >> sys.stderr, "Domain {name} was shut down...".format(name=name)
        except Exception as e:
            print >> sys.stderr, "Domain {name} was NOT shut down...\n{e}".format(name=name, e=str(e))


def remove_all_imgs(lab_img_path):
    if os.path.exists(lab_img_path):
        for i in os.listdir(lab_img_path):
            os.remove(os.path.join(lab_img_path, i))

def found_pool(pool_name):
    try:
        pool = conn.storagePoolLookupByName(pool_name)
        return pool
    except libvirtError:
        return None

def make_network_name(lab, name):
    return lab + "-net-" + name
