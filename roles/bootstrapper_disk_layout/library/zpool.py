#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2018, Remy Mudingay <remy.mudingay[at]esss.se>
# Copyright: (c) 2018, Stephane Armanet <stephane.armanet[at]esss.se>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: zpool
short_description: Manage zfs zpools
version_added: '2.8'
description:
  - Manage virtual storage pools using zfs zpools.
options:
  name:
    description:
      - The name of the pool.
    type: str
    required: true
  add:
    description:
      - Add devices (spare or mirror) to an existing zpool.
    type: bool
    default: false
  raid_level:
    description:
      - The RAID level of the pool.
    type: str
    choices: [ raid0, mirror, raidz, raidz1, raidz2, raidz3 ]
  vdevs:
    description:
      - The number of devices in a vdev.
    type: int
  devices:
    description:
      - List of block devices such as hdd, nvme or file.
    type: list
  ashift:
    description:
      - Alignment shift can be used to improve performance and is set once during the creation.
    type: int
    choices: [ 0, 9, 10, 11, 12, 13, 14, 15, 16 ]
    default: 0
  sets:
    description:
      - Set options for existing pools.
    type: bool
    default: false
  autoreplace:
    description:
      - Automatically replace a bad device in pool using a spare device.
    type: bool
    default: false
  autoexpand:
    description:
      - Whether to enable or disable automatic pool expansion when a larger disk replaces a smaller disk.
    type: bool
  spare:
    description:
      - A list of block devices such as hdd, nvme or nvme.
    type: list
  zil:
    description:
      - ZFS intent log device or devices when mirrored.
    type: str
  l2arc:
    description:
      - ZFS cache device or devices.
    type: str
  state:
    description:
      - Create or delete the pool
    type: str
    choices: [ absent, present ]
    default: present
author:
- Remy Mudingay (@rmudingay)
'''

EXAMPLES = r'''
- name: Create a new raidz zpool
  zpool:
    name: zfspool
    devices:
      - /dev/sdc
      - /dev/sdd
      - /dev/sde
    raid_level: raidz
    zil: mirror /dev/sdf /dev/sdg
    vdevs: 3
    state: present

- name: Create a new raid 0 stripe zpool
  zpool:
    name: zfspool
    devices:
      - /dev/sdb
      - /dev/sdc
      - /dev/sdd
      - /dev/sde
      - /dev/sdf
    raid_level: raid0
    l2arc: /dev/sdg
    vdevs: 5
    ashift: 12
    state: present

- name: Create a new mirror zpool
  zpool:
    name: rpool
    devices:
      - /dev/sdb
      - /dev/sdc
      - /dev/sdd
      - /dev/sde
    raid_level: mirror
    spare:
      - /dev/sdf
      - /dev/sdg
    zil: mirror /dev/sdh /dev/sdi
    l2arc: /dev/sdj
    autoreplace: true
    ashift: 12
    vdevs: 2
    state: present

- name: Create a new mirror zpool with a spare drive
  zpool:
    name: rpool
    devices:
      - /dev/sdc
      - /dev/sdd
    raid_level: mirror
    vdevs: 2
    autoreplace: true
    autoexpand: true
    spare:
      - /dev/sde
    state: present

- name: Add devices to an existing zpool
  zpool:
    name: rpool
    add: true
    devices:
    - /dev/sdf
    - /dev/sdg
    raid_level: mirror
    autoexpand: true
    vdevs: 2
    state: present

- name: Add spare dev to an existing zpool
  zpool:
    name: rpool
    add: true
    autoreplace: true
    spare:
    - /dev/sdf
    state: present

- name: Set options to an existing zpool
  zpool:
    name: zpool
    sets: true
    autoreplace: true
    state: present

- name: Set options to an existing zpool
  zpool:
    name: zpool
    sets: true
    autoexpand: off
    state: present

- name: Destroy an existing zpool
  zpool:
    name: rpool
    state: absent
'''

RETURN = r''' # '''

import ntpath
import os
import re
import subprocess

from ansible.module_utils.basic import AnsibleModule


class Zpool(object):

    def __init__(self, module, name, state, raid_level, devices, spare, add, vdevs, ashift, sets, autoreplace, autoexpand, zil, l2arc):
        self.module = module
        self.name = name
        self.raid_level = raid_level
        self.devices = devices
        self.spare = spare
        self.state = state
        self.add = add
        self.vdevs = vdevs
        self.ashift = ashift
        self.sets = sets
        self.autoreplace = autoreplace
        self.autoexpand = autoexpand
        self.zil = zil
        self.l2arc = l2arc
        self.changed = False
        self.zpool_cmd = module.get_bin_path('zpool', True)

    def exists(self):
        cmd = [self.zpool_cmd, 'list', self.name]
        (rc, out, err) = self.module.run_command(' '.join(cmd))
        if rc == 0:
            return True
        else:
            return False

    def dev_exists(self):
        cmd = [self.zpool_cmd, "list -v"]
        (rc, out, err) = self.module.run_command(' '.join(cmd), use_unsafe_shell=True)
        if rc == 0:
            return out
        else:
            return False

    def opt_exists(self):
        cmd = self.zpool_cmd, "get all ", self.name
        (rc, out, err) = self.module.run_command(' '.join(cmd), use_unsafe_shell=True)
        if rc == 0:
            col1 = [col.split()[1] for col in out.splitlines()]
            col2 = [col.split()[2] for col in out.splitlines()]
            output = col1 + col2
            return output
        else:
            return []

    def create(self):
        if self.module.check_mode:
            self.changed = True
            return
        cmd = [self.zpool_cmd]
        if self.add:
            action = 'add'
        elif self.sets:
            action = 'set'
        else:
            action = 'create'
        cmd.append(action)
        if action == 'create':
            if self.ashift and action == 'create':
                ashift = '-o ashift=' + str(self.ashift)
            else:
                ashift = '-o ashift=0'
            cmd.append(ashift)
        cmd.append(self.autoreplace)
        cmd.append(self.autoexpand)
        cmd.append(self.name)
        if action != 'set':
            cmd.append(self.devices)
            cmd.append(self.spare)
            cmd.append(self.zil)
            cmd.append(self.l2arc)
        (rc, out, err) = self.module.run_command(' '.join(cmd))
        if rc == 0:
            self.changed = True
        else:
            self.module.fail_json(msg=err)

    def destroy(self):
        if self.module.check_mode:
            self.changed = True
            return
        cmd = [self.zpool_cmd, 'destroy', self.name]
        (rc, out, err) = self.module.run_command(' '.join(cmd))
        if rc == 0:
            self.changed = True
        else:
            self.module.fail_json(msg=err)


def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def main():

    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            state=dict(type='str', default='present', choices=['absent', 'present']),
            raid_level=dict(type='str', required=False, choices=['raid0', 'mirror', 'raidz', 'raidz1', 'raidz2', 'raidz3']),
            vdevs=dict(aliases=['vdev'], type='int', require=False),
            devices=dict(type='list'),
            spare=dict(type='list'),
            add=dict(type='bool', default=False),
            ashift=dict(type='int', default=0, choices=[0, 9, 10, 11, 12, 13, 14, 15, 16]),
            sets=dict(type='bool', default=False),
            autoreplace=dict(type='bool'),
            autoexpand=dict(type='bool'),
            zil=dict(type='str'),
            l2arc=dict(type='str'),
        ),
        supports_check_mode=True,
        required_together=[['raid_level', 'devices'], ['devices', 'vdevs']],
        mutually_exclusive=[['add', 'sets']]
    )

    name = module.params.get('name')
    state = module.params.get('state')
    add = module.params.get('add')
    raid_level = module.params.get('raid_level')
    devices = module.params.get('devices')
    spare = module.params.get('spare')
    vdevs = module.params.get('vdevs')
    ashift = module.params.get('ashift')
    sets = module.params.get('sets')
    autoreplace = module.params.get('autoreplace')
    autoexpand = module.params.get('autoexpand')
    l2arc = module.params.get('l2arc')
    zil = module.params.get('zil')

    if autoexpand is True and (sets is True or add is True):
        autoexpand = "autoexpand=on"
    elif autoexpand is True and sets is False:
        autoexpand = "-o autoexpand=on"
    elif autoexpand is False and sets is True:
        autoexpand = "autoexpand=off"
    else:
        autoexpand = ""

    if autoreplace is True and (sets is True or add is True):
        autoreplace = "autoreplace=on"
    elif autoreplace is True and sets is False:
        autoreplace = "-o autoreplace=on"
    elif autoreplace is False and sets is True:
        autoreplace = "autoreplace=off"
    else:
        autoreplace = ""

    if raid_level is None or 'raid0' in raid_level:
        raid_level = ''

    if zil:
        zil = ' log ' + zil
    else:
        zil = ''

    if l2arc:
        l2arc = ' cache ' + l2arc
    else:
        l2arc = ''

    if ashift is None:
        ashift = 0

    if not devices:
        devices = ''
    else:
        if vdevs > 1:
            device = ''
            for i in range(0, len(devices), vdevs):
                temp = ' ' + raid_level + ' ' + ' '.join(devices[i:i + vdevs])
                device += temp
            devices = device
    if not spare:
        spare = ''
    else:
        spare = 'spare ' + ' '.join(spare)

    result = dict(
        name=name,
        state=state,
        raid_level=raid_level,
        devices=devices,
        spare=spare,
        vdevs=vdevs,
        sets=sets,
        ashift=ashift,
        autoreplace=autoreplace,
        autoexpand=autoexpand,
        zil=zil,
        l2arc=l2arc,
    )

    zpool = Zpool(module, name, state, raid_level, devices, spare, add, vdevs, ashift, sets, autoreplace, autoexpand, zil, l2arc)

    if state == 'present':
        if (zpool.exists() and add) or (zpool.exists() and sets) or (zpool.exists() is False):
            if zpool.dev_exists():
                outlist = zpool.dev_exists().split()
                if devices:
                    device_out = devices.split()
                    device_output = [path_leaf(path) for path in device_out]
                    do = bool(set(outlist) & set(device_output))
                else:
                    do = False
                if spare:
                    spare_out = spare.split()
                    spare_output = [path_leaf(path) for path in spare_out]
                    so = bool(set(outlist) & set(spare_output))
                else:
                    so = False
                if zil:
                    zil_out = zil.split()
                    zil_output = [path_leaf(path) for path in zil_out]
                    zo = bool(set(outlist) & set(zil_output))
                else:
                    zo = False
                if l2arc:
                    l2arc_out = l2arc.split()
                    l2arc_output = [path_leaf(path) for path in l2arc_out]
                    lo = bool(set(outlist) & set(l2arc_output))
                else:
                    lo = False
                optlist = zpool.opt_exists()
                ae = False
                if autoexpand:
                    if 'on' in autoexpand:
                        if 'autoexpandon' in optlist:
                            ae = True
                    elif 'off' in autoexpand:
                        if 'autoexpandoff' in optlist:
                            ae = True
                else:
                    ae = False
                ar = False
                if autoreplace:
                    if 'on' in autoreplace:
                        if 'autoreplaceon' in optlist:
                            ar = True
                    elif 'off' in autoreplace:
                        if 'autoreplaceoff' in optlist:
                            ar = True
                else:
                    ar = False
                if (do or so or zo or lo or ae or ar) is False:
                    zpool.create()
            else:
                zpool.create()
    elif state == 'absent':
        if zpool.exists():
            zpool.destroy()

    result['changed'] = zpool.changed
    module.exit_json(**result)


if __name__ == '__main__':
    main()
