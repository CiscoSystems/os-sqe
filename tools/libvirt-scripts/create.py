#!/usr/bin/python
import libvirt
import argparse
import random
import yaml
import os
import re
import sys
import logging
import subprocess

from xml.etree import ElementTree as et
from tempfile import mkstemp
from libvirt import libvirtError

__author__ = 'sshnaidm'


def rand_mac():
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(["%02x" % x for x in mac])

## TODO: remove GLOBALS
name_woext = "trusty-server-cloudimg-amd64-disk1"
EXTERNAL_NET = "external"
DOMAIN_NAME = "domain.name"


def handler(ctxt, err):
    global errno
    errno = err
libvirt.registerErrorHandler(handler, 'context')


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


def vm_create(conn, xml):
    return conn.defineXML(xml)


def net_create(conn, xml):
    net = conn.networkDefineXML(xml)
    net.create()
    net.setAutostart(True)
    return net


def net_undefine(conn, net_name):
    try:
        net = conn.networkLookupByName(net_name)
    except libvirtError:
        print >> sys.stderr, "Net wans't found, nothing to delete"
        return
    try:
        net.destroy()
    except libvirtError:
        print >> sys.stderr, "Net wans't active, nothing to delete"
        return
    net.undefine()


def pool_delete(conn, name):
    try:
        pool = conn.storagePoolLookupByName(name)
    except libvirtError:
        print >> sys.stderr, "Pool not found, nothing to delete"
        return
    try:
        pool.destroy()
    except libvirtError:
        print >> sys.stderr, "Pool wans't active, just undefine it"
    pool.undefine()


def pool_create(conn, xml):
    pool = conn.storagePoolDefineXML(xml)
    pool.create()
    pool.setAutostart(True)
    return pool


def pool_found(conn, name):
    try:
        conn.storagePoolLookupByName(name)
        return True
    except libvirtError:
        return False


def convert_image(path, new_path):
    ret, ignore, stderr = run_cmd(["qemu-img", "convert", "-O",
                                   "qcow2", path, new_path])
    print >> sys.stderr, "\n".join(ignore), "\n".join(stderr)
    if ret == 127:
        ret, ignore, stderr = run_cmd(["kvm-img", "convert", "-O",
                                       "qcow2", path, new_path])
    if ret != 0:
        raise RuntimeError("Disk conversion failed with "
                           "exit status %d: %s" % (ret, "".join(stderr)))
    #if len(stderr):
    #    print >> sys.stderr, stderr


def main_disk_create(name="", size=0, config=None, conn=None, img_path="", boot_type="net", user_seed_yaml=None,
                     img_uncomp_path=None, lab_id="lab1"):
    path = os.path.join(img_path, name + ".qcow2")
    size_bytes = size*1024*1024*1024
    if boot_type == "net":
        vol_xml = config["params"]["vol"]["xml"].format(name=name, size=size_bytes, path=path)
        #_, tmp_file = mkstemp(prefix="disk_vol_")
        #with open(tmp_file, "w") as f:
        #    f.write(vol_xml)
        #run_cmd(["virsh", "vol-create",  "--pool", "default-" + lab_id, "--file", tmp_file])
        pool = conn.storagePoolLookupByName("default-" + lab_id)
        vol = pool.createXML(vol_xml, 1)
        #os.remove(tmp_file)
        return config["params"]["vol"]["virt_disk"].format(output_file=path)
    elif boot_type == "cloudimg":
        seed_disk = os.path.join(img_path, name + "-seed.qcow2")
        #img_uncomp_path=os.path.join(IMG_PATH, "lab-backing.qcow2")
        _, tmp_file = mkstemp(prefix="useryaml_")
        with open(tmp_file, "w") as f:
            f.write("#cloud-config\n" + user_seed_yaml)
        run_cmd(["qemu-img", "create", "-f", "qcow2", "-b", img_uncomp_path, path, "%sG" % size])
        run_cmd(["cloud-localds", seed_disk, tmp_file])
        os.remove(tmp_file)
        return config["params"]["vol"]["cloudimg_disk"].format(output_file=path, seed_disk=seed_disk)


def create_vm(conn, xml):
    vm = conn.defineXML(xml)
    vm.create()
    return vm


def delete_vm(conn, name):
    try:
        vm = conn.lookupByName(name)
    except libvirtError:
        print >> sys.stderr, "Domain {name} not found, nothing to delete".format(name=name)
        return
    try:
        vm.destroy()
    except libvirtError:
        pass
    vm.undefine()
    print >> sys.stderr, "Domain {name} deleted".format(name=name)


def remove_all_imgs(img_path, lab_id):
    if os.path.exists(img_path):
        for i in [j for j in os.listdir(img_path) if lab_id in j]:
            os.remove(os.path.join(img_path, i))


def create_seed_yaml(config, box=None):
    if not box:
        return None
    user_seed_yaml_string = config['params'][box]['user-yaml']
    user_seed_yaml = yaml.load(user_seed_yaml_string)
    user_seed_yaml['users'][1]['ssh-authorized-keys'] = config['params']['id_rsa_pub']
    user_seed_yaml['users'][1]['passwd'] = ("$6$rounds=4096$A0eKrix5oH$4F70Syi4jfhMCRygdOUC.d.qItQ57KsmW8"
                                            "CHhs42r/bPm7ySXdYLoHCdpg3SLlWZlv9FnRAUhgp8C23DiVZr9.")
    user_seed_yaml['write_files'][0]['content'] = "\n".join(config['params']['id_rsa_pub'])
    return yaml.dump(user_seed_yaml)


def create_host_seed_yaml(config, box, btype):
    user_seed_yaml_string = config['params'][btype]['user-yaml']
    user_seed_yaml = yaml.load(user_seed_yaml_string)
    user_seed_yaml['users'][1]['ssh-authorized-keys'] = config['params']['id_rsa_pub']
    user_seed_yaml['users'][1]['passwd'] = ("$6$rounds=4096$A0eKrix5oH$4F70Syi4jfhMCRygdOUC.d.qItQ57KsmW8"
                                            "CHhs42r/bPm7ySXdYLoHCdpg3SLlWZlv9FnRAUhgp8C23DiVZr9.")
    user_seed_yaml['write_files'][0]['content'] = "\n".join(config['params']['id_rsa_pub'])
    ints = []
    last_octet = box['ip'].split(".")[-1]
    #sorted_nets = sorted(networks.keys(), key=lambda x: int(networks[x]["net-ip"].split(".")[2]))
    sorted_nets = config['params']['networks']
    parsed = et.fromstring(config['params'][btype]['xml'])
    used_nets = [i.attrib['network'] for i in parsed.findall(".//interface[@type='network']/source")]
    index_net = 1
    for k, net in enumerate(sorted_nets[1:]):
        if "{net_" + net['role'] + "_name}" in used_nets:
            if net['role'] != EXTERNAL_NET:
                ints.append([
                    config['params']['static_interface_template'].format(
                        int_name="eth"+str(index_net),
                        net_ip=net['net-ip'],
                        int_ip=net['net-ip'] + "." + last_octet,
                        dns="8.8.8.8"),
                    "/etc/network/interfaces.d/eth{int_num}.cfg".format(int_num=index_net),
                    "eth{int_num}".format(int_num=index_net)
                ])
            else:
                ints.append([
                    config['params']['manual_interface_template'].format(
                        int_name="eth"+str(index_net),),
                    "/etc/network/interfaces.d/eth{int_num}.cfg".format(int_num=index_net),
                    "eth{int_num}".format(int_num=index_net)
                    ])
            index_net += 1
        else:
            continue
    for interface in ints:
        user_seed_yaml["write_files"].append({
            "content": interface[0],
            "path": interface[1],
            })
    hosts_file = config['params']['hosts_template'].format(
        server_name=box["hostname"],
        domain_name=DOMAIN_NAME,
    )
    user_seed_yaml["write_files"].append({
        "content": hosts_file,
        "path": "/etc/hosts",
        })
    ## I'm really tired to investigate why this doesn't work!!!!
    #hostname_file = config['params']['hostname_template'].format(
    #    server_name=box["hostname"],
    #)
    #user_seed_yaml["write_files"].append({
    #    "content": hostname_file,
    #    "path": "/etc/hostname",
    #    })
    full_cmd = []
    for cmd in user_seed_yaml['runcmd']:
        if "hostname" in cmd:
            full_cmd.append("/bin/hostname " + box["hostname"])
            full_cmd.append("/bin/echo " + box["hostname"] + " > /etc/hostname")
        elif "ifdown" in cmd:
            for interf in ints:
                int_name = interf[2]
                full_cmd.append("/sbin/ifdown {int} && /sbin/ifup {int}".format(int=int_name))
            full_cmd.append("/etc/init.d/networking restart")
        else:
            full_cmd.append(cmd)
    user_seed_yaml['runcmd'] = full_cmd
    return yaml.dump(user_seed_yaml)


def delete_all(conn=None, lab_id=None, img_path=None, conf=None):
    if img_path:
        remove_all_imgs(img_path, lab_id)
    if conf:
        for i in [j for j in conf['params'] if "server" in j]:
            basic_name = lab_id + "-" + i.split(".")[0]
            delete_vm(conn, basic_name)
            for num in xrange(10):
                delete_vm(conn, basic_name + "%.2d" % num)
        for net in conf['params']['networks']:
            basic_net_name = lab_id + "-" + net['name']
            net_undefine(conn, basic_net_name)
        pool_delete(conn, "default-" + lab_id)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-a', action='store', dest='host', default=None,
                        help='Host for action')
    parser.add_argument('-b', action='store', dest='boot', default="cloudimg",
                        choices=['net', 'cloudimg'], help='Boot')
    parser.add_argument('-k', action='store', dest='computes', type=int, default=1,
                        help='How many compute servers')
    parser.add_argument('-n', action='store', dest='controls', type=int, default=1,
                        help='How many control servers')
    parser.add_argument('-l', action='store', dest='labid', default="lab1",
                        help='Lab ID in configuration, default=lab1')
    parser.add_argument('-g', action='store', dest='cpus', type=int, default=1,
                        help='How many cpu for compute servers')
    parser.add_argument('-d', action='store', dest='img_dir', default="/opt/imgs",
                        help='Where to store all images and disks, full abs path')
    parser.add_argument('-z', action='store', dest='ubuntu_img_dir',
                        default="/opt/iso/trusty-server-cloudimg-amd64-disk1.img",
                        help='Where to find downloaded cloud image, full abs path')
    parser.add_argument('-o', action='store_true', dest='aio_mode', default=False,
                        help='Create only "all in one" setup')
    parser.add_argument('-x', action='store_true', dest='undefine_all', default=False,
                        help='Undefine everything with this lab_id')

    opts = parser.parse_args()
    user = opts.user
    host = opts.host
    control_servers_len = opts.controls
    compute_servers_len = opts.computes
    lab_id = opts.labid
    compute_cpus = opts.cpus
    img_path = opts.img_dir
    ubuntu_img_path = opts.ubuntu_img_dir
    aio_mode = opts.aio_mode
    conn = libvirt.open('qemu+ssh://{user}@{host}/system'.format(user=user, host=host))

    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "box.yaml")) as f:
        conf = yaml.load(f)
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates", "env.yaml")) as f:
        env = yaml.load(f)

    if opts.undefine_all:
        if opts.labid:
            delete_all(conn=conn, lab_id=lab_id, img_path=img_path, conf=conf)
            return
        else:
            print >> sys.stderr, "Please provide lab id"
            sys.exit(1)

    ip_start = env[lab_id]['ip_start']
    net_start = env[lab_id]['net_start']
    if aio_mode:
        lab_boxes = {
            "aio-servers": [],
        }
        control_servers_len = compute_servers_len = 0
    else:
        lab_boxes = {
            "compute-servers": [],
            "build-server": [],
            "control-servers": [],
        }

    ######### NETWORKS

    networks = conf['params']['networks']
    for num, net in enumerate(networks):
        net['net-ip'] = "192.168." + str(net_start + num)
        net['name'] = lab_id + "-" + net['name']
        if net['role'] == EXTERNAL_NET:
            external_net_subnet = net['net-ip']

    dhcp_hostline = '<host mac="{server_mac}" name="{server_name}.domain.name" ip="{server_ip}" />'
    dhcp_records = ''
    mac = rand_mac()
    ip = networks[0]["net-ip"] + "." + str(ip_start)
    if "build-server" in lab_boxes:
        dhcp_records = dhcp_hostline.format(
            server_mac=mac,
            server_name="build-server",
            server_ip=ip)
        lab_boxes["build-server"].append({
            "hostname": "build-server",
            "name": lab_id + "-build-server",
            "ip": ip,
            "mac": mac
            })
    if "aio-servers" in lab_boxes:
        dhcp_records = dhcp_hostline.format(
            server_mac=mac,
            server_name="all-in-one",
            server_ip=ip)
        lab_boxes["aio-servers"].append({
            "hostname": "all-in-one",
            "name": lab_id + "-aio-server",
            "ip": ip,
            "mac": mac
            })
    for i in xrange(control_servers_len):
        mac = rand_mac()
        ip = networks[0]["net-ip"] + "." + str(ip_start + i + 1)
        dhcp_records += "\n" + dhcp_hostline.format(
            server_mac=mac,
            server_name="control-server%.2d" % i,
            server_ip=ip)
        lab_boxes["control-servers"].append({
            "hostname": "control-server%.2d" % i,
            "name": lab_id + "-control-server%.2d" % i,
            "ip": ip,
            "mac": mac})
    ip_start += control_servers_len
    for i in xrange(compute_servers_len):
        mac = rand_mac()
        ip = networks[0]["net-ip"] + "." + str(ip_start + i + 1)
        dhcp_records += "\n" + dhcp_hostline.format(
            server_mac=mac,
            server_name="compute-server%.2d" % i,
            server_ip=ip)
        lab_boxes["compute-servers"].append({
            "hostname": "compute-server%.2d" % i,
            "name": lab_id + "-compute-server%.2d" % i,
            "ip": ip,
            "mac": mac})

    for net in networks:
        net_undefine(conn, net['name'])
        net_xml = net['xml'].format(name=net['name'], net_ip=net["net-ip"], dhcp_records=dhcp_records)
        net_create(conn, net_xml)

    ############ BOXES ############
    remove_all_imgs(img_path, lab_id)
    pool_name = "default-" + lab_id
    if opts.boot == "net":
        if pool_found(conn, pool_name):
            pool_delete(conn, pool_name)
        pool_create(conn, conf['params']['pool']['xml'].format(
            name=pool_name, path=img_path))

    new_img_path = os.path.join(img_path, lab_id + "-backing.img")
    convert_image(ubuntu_img_path, new_img_path)
    final_result = {"servers": None}

    # create aio server if configured
    if aio_mode:
        aio = lab_boxes['aio-servers'][0]
        yaml_config = create_host_seed_yaml(conf, box=aio, btype="aio-server")
        conf_yaml = yaml.load(yaml_config)
        disk = main_disk_create(name=aio["name"],
                                size=10,  # in GB
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["aio-server"]["xml"].format(
            name=aio["name"],
            ram=8*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=aio["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        delete_vm(conn, aio["name"])
        create_vm(conn, vm_xml)
        conn.close()
        eth_default = re.search("(eth\d+)",
                                [z for z in conf_yaml["write_files"]
                                    if 'inet static' in z['content']][0]['content']).group(1)
        eth_external = re.search("(eth\d+)",
                                 [z for z in conf_yaml["write_files"]
                                  if 'inet manual' in z['content']][0]['content']).group(1)
        default_net_subnet = re.search("network ([^\s]+)",
                                       [z for z in conf_yaml["write_files"]
                                        if 'inet static' in z['content']][0]['content']).group(1)
        final_result["servers"] = {
            "aio": {
                "ip": aio["ip"],
                "mac": aio["mac"],
                "vm_name": aio["name"],
                "user": "root",
                "password": "ubuntu",
                "external_interface": eth_external,
                "default_interface": eth_default,
                "external_net": external_net_subnet + ".0",
                "default_net": default_net_subnet,
            }
        }
        print yaml.dump(final_result)
        # workaround for tempest nets configurator
        with open("external_net", "w") as f:
            f.write(external_net_subnet)
        print >> sys.stderr, "Created AIO box", aio["name"], "with ip", aio["ip"]
        return

    # create build server
    build = lab_boxes["build-server"][0]
    yaml_config = create_host_seed_yaml(conf, box=build, btype="build-server")
    conf_yaml = yaml.load(yaml_config)
    disk = main_disk_create(name=build["name"],
                            size=10,  # in GB
                            config=conf,
                            conn=conn,
                            boot_type="cloudimg",
                            img_path=img_path,
                            user_seed_yaml=yaml_config,
                            img_uncomp_path=new_img_path,
                            lab_id=lab_id)
    vm_xml = conf["params"]["build-server"]["xml"].format(
        name=lab_boxes["build-server"][0]["name"],
        ram=8*1024*1024,
        disk=disk,
        net_boot_name=conf["params"]["networks"][0]["name"],
        build_server_mac=lab_boxes["build-server"][0]["mac"],
        net_admin_name=conf["params"]["networks"][1]["name"],
        net_external_name=conf["params"]["networks"][4]["name"],
    )
    delete_vm(conn, lab_boxes["build-server"][0]["name"])
    create_vm(conn, vm_xml)
    eth_external = re.search("(eth\d+)",
                                 [z for z in conf_yaml["write_files"]
                                  if 'inet manual' in z['content']][0]['content']).group(1)
    final_result["servers"] = {
        "build-server": {
            "ip": build["ip"],
            "mac": build["mac"],
            "hostname": build["hostname"],
            "vm_name": build["name"],
            "user": "root",
            "password": "ubuntu",
            "default_interface": "eth1",
            "external_interface": eth_external,
            "external_net": external_net_subnet + ".0",
        }
    }
    print >> sys.stderr, "Created build-server", lab_boxes["build-server"][0]["name"], \
        "with ip", lab_boxes["build-server"][0]["ip"]

    with open("external_net", "w") as f:
            f.write(external_net_subnet)

    ### create other servers
    for compute in lab_boxes["compute-servers"]:
        yaml_config = create_host_seed_yaml(conf, box=compute, btype="compute-server")
        disk = main_disk_create(name=compute["name"],
                                size=10,  # in GB
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["compute-server"]["xml"].format(
            name=compute["name"],
            ram=4*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=compute["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_public_name=conf["params"]["networks"][2]["name"],
            net_internal_name=conf["params"]["networks"][3]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        delete_vm(conn, compute["name"])
        create_vm(conn, vm_xml)
        compute_box_config = {
            "ip": compute["ip"],
            "mac": compute["mac"],
            "hostname": compute["hostname"],
            "vm_name": compute["name"],
            "user": "root",
            "password": "ubuntu",
            "admin_interface": "eth1",
            "public_interface": "eth2",
            "internal_interface": "eth3",
            "external_interface": "eth4",
        }
        if "compute-servers" in final_result["servers"]:
            final_result["servers"]["compute-servers"].append(compute_box_config)
        else:
            final_result["servers"]["compute-servers"] = [compute_box_config]
        print >> sys.stderr, "Created compute-server", compute["name"], "with ip", compute["ip"]

    for control in lab_boxes["control-servers"]:
        yaml_config = create_host_seed_yaml(conf, box=control, btype="control-server")
        disk = main_disk_create(
                                name=control["name"],
                                size=10,
                                config=conf,
                                conn=conn,
                                boot_type=opts.boot,
                                img_path=img_path,
                                user_seed_yaml=yaml_config,
                                img_uncomp_path=new_img_path,
                                lab_id=lab_id)
        vm_xml = conf["params"]["control-server"]["xml"].format(
            name=control["name"],
            ram=4*1024*1024,
            disk=disk,
            compute_server_cpu=compute_cpus,
            net_boot_name=conf["params"]["networks"][0]["name"],
            mac=control["mac"],
            net_admin_name=conf["params"]["networks"][1]["name"],
            net_public_name=conf["params"]["networks"][2]["name"],
            net_internal_name=conf["params"]["networks"][3]["name"],
            net_external_name=conf["params"]["networks"][4]["name"],
        )
        delete_vm(conn, control["name"])
        create_vm(conn, vm_xml)
        control_box_config = {
            "ip": control["ip"],
            "mac": control["mac"],
            "hostname": control["hostname"],
            "vm_name": control["name"],
            "user": "root",
            "password": "ubuntu",
            "admin_interface": "eth1",
            "public_interface": "eth2",
            "internal_interface": "eth3",
            "external_interface": "eth4",
        }
        if "control-servers" in final_result["servers"]:
            final_result["servers"]["control-servers"].append(control_box_config)
        else:
            final_result["servers"]["control-servers"] = [control_box_config]
        print >> sys.stderr, "Created control-server", control["name"], "with ip", control["ip"]
    #boxes = conn.listAllDomains()
    #for b in boxes:
    #    print b.name()
    print yaml.dump(final_result)
    conn.close()


if __name__ == "__main__":
    main()
