#!/usr/bin/env python

__author__ = 'sshnaidm'

import os, sys, time, random
prefix = "/tmp/lock.lab"
TIMEOUT = 1800

if "POOL" not in os.environ:
    sys.exit(1)
pool = os.environ["POOL"].split("-")
if len(pool) !=2:
    sys.exit(1)
try:
    pool = [int(i) for i in pool]
    pool_range = xrange(pool[0], pool[1] + 1)
except:
    sys.exit(1)

lab_num = None
start = time.time()
while time.time() - start < TIMEOUT and not lab_num:
    for ind in pool_range:
        if not os.path.exists(prefix + str(ind)):
            lab_num = str(ind)
            with open(prefix + lab_num, "w") as f:
                f.write("lock")
            break
    else:
        time.sleep(random.randint(20, 40))
if not lab_num:
    sys.exit(1)
else:
    sys.stdout.write("lab" + lab_num)
    sys.exit(0)