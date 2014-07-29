import os
import sys
import yaml
import string


from cloudtools import conn, found_pool
from config import TEMPLATE_PATH, opts
from cloudseed import SeedStorage

with open(os.path.join(TEMPLATE_PATH, "storage.yaml")) as f:
    storconf = yaml.load(f)


class Storage:
    disks = {}

    def __init__(self, lab_id, config, path, boot, box, cloud_disk):
        self.boot = boot
        self.lab_id = lab_id
        self.full_conf = config
        self.path = path
        self.cloud_disk_path = cloud_disk
        self.pool_name = lab_id + "-default"
        self.pool = None
        self.server = box
        self.conf = config["servers"][box]
        self.distro = opts.distro

    def box_name(self, num):
        return self.lab_id + "-" + self.server + "%.2d" % num if self.conf['params']['count'] != 1 \
            else self.lab_id + "-" + self.server

    def pool_define(self):
        return storconf["pool"]["xml"].format(
            name=self.pool_name,
            path=self.path,
        )

    def pool_create(self):
        pool_xml = self.pool_define()
        self.pool_obj = conn.storagePoolDefineXML(pool_xml)
        self.pool_obj.create()
        self.pool_obj.setAutostart(True)

    def virtual_disk_define(self):
        xmls = []
        for num in xrange(self.conf["params"]["count"]):
            name = self.box_name(num=num) + ".qcow2"
            disk_path = os.path.join(self.path, name)
            size_bytes = self.conf["params"]["storage"]*1024*1024*1024
            disk_xml = storconf['vol']['xml'].format(name=name, size=size_bytes, path=disk_path)
            self.pool.createXML(disk_xml, 1)
            xmls.append(storconf['vol']["regular_disk"].format(output_file=disk_path))
        return xmls

    def cloud_disk_define(self):
        xmls = []
        for num in xrange(self.conf["params"]["count"]):
            name = self.box_name(num=num) + ".qcow2"
            disk_path = os.path.join(self.path, name)
            size_bytes = self.conf["params"]["storage"]*1024*1024*1024
            disk_xml = storconf['vol']['cloudimg'].format(
                name=name,
                size=size_bytes,
                disk_path=disk_path,
                img_disk_path=self.cloud_disk_path
            )
            self.pool.createXML(disk_xml, 0)
            xmls.append(storconf['vol']["regular_disk"].format(output_file=disk_path))
        return xmls

    def seed_disk(self):
        xmls = []
        for num in xrange(self.conf["params"]["count"]):
            name = self.box_name(num=num) + "-seed.qcow2"
            disk_path = os.path.join(self.path, name)
            xmls.append(storconf['vol']['seed_disk'].format(seed_disk=disk_path))
            seed = SeedStorage(self.lab_id, self.server, disk_path, num, self.full_conf)
            seed.create()
        return xmls

    def storage_disk(self):
        xmls = []
        for num in xrange(self.conf['params']['count']):
            xmls.append([])
            targets = iter(["vd" + i for i in string.ascii_lowercase[1:]])
            for disk in xrange(1, self.conf['params']['add_disks'][0] + 1):
                name = self.box_name(num=num) + "-add%.2d.qcow2" % disk
                disk_path = os.path.join(self.path, name)
                disk_add_xml = storconf['vol']['xml'].format(
                    name=name,
                    size=self.conf['params']['add_disks'][1]*1024*1024*1024,
                    path=disk_path
                )
                self.pool.createXML(disk_add_xml, 0)
                disk_add = storconf['vol']['storage_disk'].format(output_file=disk_path, target=targets.next())
                xmls[num].append(disk_add)
        return xmls

    def setup(self):
        if not os.path.isdir(self.path):
            try:
                os.makedirs(self.path)
            except IOError:
                print >> sys.stderr, "Can not create directory {dir} that doesn't exist!".format(dir=self.path)
                sys.exit(1)
        self.pool = found_pool(self.pool_name)
        if not self.pool:
            self.pool_create()
            self.pool = found_pool(self.pool_name)
        if self.boot == "net" and self.server != "build-server":
            xmls = self.virtual_disk_define()
        else:
            xmls = ["\n".join(i) for i in zip(self.cloud_disk_define(), self.seed_disk())]
        if self.conf["params"]["add_disks"]:
            xmls_add = self.storage_disk()
        for num in xrange(self.conf['params']['count']):
            name = self.box_name(num)
            self.disks[name] = xmls[num]
            if self.conf["params"]["add_disks"]:
                self.disks[name] += "\n".join(xmls_add[num])

