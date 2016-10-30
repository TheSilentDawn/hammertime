#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright (c) 2016 Andrei Tatar
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tool to autodetect running memory system and produce msys files."""

import re
import os
import math
import subprocess

from collections import namedtuple

CONTROLLERS = [
    'naive_ddr3',
    'naive_ddr4',
    'intel_sandy',
    'intel_ivy',
    'intel_haswell'
]

ROUTERS = [
    'passthru',
    'x86_generic',
]

REMAPS = [
    'none',
    'r3x0',
    'r3x21',
    'r3x210',
]

def _ask(name, lst):
    print('Select {}:'.format(name))
    while True:
        for i, s in enumerate(lst):
            print('\t{}. {}'.format(i, s))
        inp = input('Choice: ')
        try:
            return lst[int(inp)]
        except (ValueError, IndexError):
            pass

_X86_SMM = namedtuple('_SMM', ['remap', 'hasME', 'pci_start', 'topmem'])
_GEOM = namedtuple('_GEOM', ['chans', 'dimms', 'ranks'])

def _x86_smm_detect():
    MEM_GRAN = 1 << 30 # Assume system memory is rounded to gigabytes
    iomem_rex = re.compile(r'(\w+)-(\w+)\s:\s(.+)')
    with open('/proc/iomem') as f:
        lines = [x.groups() for ln in f for x in iomem_rex.finditer(ln)]
    try:
        pci_start = int(next(x[0] for x in lines if int(x[0], 16) > 0x100000 and 'PCI' in x[-1]), 16)
    except StopIteration:
        # No PCI start address found; either insufficient permissions or not x86
        return None
    topmem = (int([x for x in lines if 'PCI' not in x[-1]][-1][1], 16) + 1) - 0x100000000 + pci_start
    topmem = math.ceil(topmem / MEM_GRAN) * MEM_GRAN
    remap = len([x for x in lines if int(x[0], 16) >= 0x100000000]) > 0
    try:
        os.stat('/dev/mei0')
        hasme = True
    except FileNotFoundError:
        hasme = False
    return _X86_SMM(remap, hasme, pci_start, topmem)

def _x86_smm_ask():
    while True:
        ans = input('PCI hole remapping active? [Y/n]: ')
        if ans == '' or ans.lower() == 'y':
            remap = True
            break
        elif ans.lower() == 'n':
            remap = False
            break
    while True:
        ans = input('Intel ME memory stealing active? [Y/n]: ')
        if ans == '' or ans.lower() == 'y':
            hasme = True
            break
        elif ans.lower() == 'n':
            hasme = False
            break
    while True:
        try:
            pci_start = int(input('PCI start address: '))
            break
        except ValueError:
            pass
    while True:
        try:
            topmem = int(input('Total memory size: '))
            break
        except ValueError:
            pass
    return _X86_SMM(remap, hasme, pci_start, topmem)

def _x86_geom_guess():
    r = subprocess.check_output(['dmidecode', '-t', 'memory'])
    dmi = r.decode('ascii').split('\n')
    sizes = [x.strip().split(': ') for x in dmi if 'Size' in x]
    used = [x[1] != 'No Module Installed' for x in sizes]
    nused = sum(used)
    ranks = [x.strip().split(': ') for x in dmi if 'Rank' in x]
    rank_guess = 1
    for i, rk in enumerate(ranks):
        if used[i]:
            try:
                rank_guess = int(rk[1])
                break
            except ValueError:
                pass
    if len(sizes) == 1:
        return _GEOM(1, 1, rank_guess)
    elif len(sizes) == 2:
        if nused == 2:
            return _GEOM(1, 2, rank_guess)
        else:
            return _GEOM(1, 1, rank_guess)
    elif len(sizes) == 4:
        if nused == 1:
            return _GEOM(1, 1, rank_guess)
        elif nused == 4:
            # Typical dual-channel dual-dimm setup
            return _GEOM(2, 2, rank_guess)
        elif nused == 2:
            if (used[0] and used[1]) or (used[2] and used[3]):
                # Typical single-channel dual-dimm setup
                return _GEOM(1, 2, rank_guess)
            elif (used[0] and used[2]) or (used[1] and used[3]):
                # Typical dual-channel single-dimm setup
                return _GEOM(2, 1, rank_guess)
            else:
                # No idea; ask user
                return None
        else:
            # No idea; ask used
            return None
    else:
        # No idea; ask user
        return None

def _geom_ask():
    while True:
        try:
            ch = int(input('Number of active channels: '))
            break
        except ValueError:
            pass
    while True:
        try:
            di = int(input('Number of DIMMs per channel: '))
            break
        except ValueError:
            pass
    while True:
        try:
            ra = int(input('Number of ranks per DIMM: '))
            break
        except ValueError:
            pass
    return _GEOM(ch, di, ra)


class MSYS(namedtuple('MSYS', ['controller', 'router', 'dimm_remap', 'geometry', 'route_opts'])):
    def to_file(self):
        lines = [
            'cntrl ' + self.controller,
            'route ' + self.router,
            'remap ' + self.dimm_remap
        ]
        if self.router == 'x86_generic':
            lines.append('route_opts {},{},{}'.format(
                self.route_opts.remap * 1 + self.route_opts.hasME * 2,
                self.route_opts.pci_start, self.route_opts.topmem
                )
            )
        if self.geometry.chans == 2:
            lines.append('chan')
        if self.geometry.dimms == 2:
            lines.append('dimm')
        if self.geometry.ranks == 2:
            lines.append('rank')

        return '\n'.join(lines) + '\n'


def _main():
    if os.geteuid() != 0:
        print("For best autodetection results it's recommended you run this tool as superuser.")
    outpath = './mem.msys'

    cntrl = _ask('memory controller', CONTROLLERS)
    route = _ask('physical address router', ROUTERS)
    remap = _ask("on-DIMM remap strategy (if unsure, select 'none')", REMAPS)
    if 'x86' in route:
        geom = _x86_geom_guess()
        smm = _x86_smm_detect()
    else:
        geom = _SMM(1, 1, 1)
        smm = None

    print('Autodetected memory geometry')
    while True:
        if geom is not None:
            print('\t{} active channels\n\t{} DIMMs per channel\n\t{} ranks per DIMM\n'.format(*geom))
            ans = input('Is this correct? [Y/n]: ')
        else:
            print('Unknown')
            ans = 'n'

        if ans == '' or ans.lower() == 'y':
            break
        elif ans.lower() == 'n':
            geom = _geom_ask()

    print('Autodetected routing options')
    while True:
        if smm is not None:
            print('PCI IOMEM start: {}; Total installed RAM: {}'.format(hex(smm.pci_start), hex(smm.topmem)))
            print('PCI memory hole remapping is [{}]'.format('enabled' if smm.remap else 'disabled'))
            print('Intel ME memory stealing is [{}]'.format('enabled' if smm.hasME else 'disabled'))
        else:
            print('None')
        ans = input('Is this correct? [Y/n]: ')
        if ans == '' or ans.lower() == 'y':
            break
        elif ans.lower() == 'n':
            smm = _x86_smm_ask()

    ans = input('Path to write output to [{}]: '.format(outpath))
    if ans:
        outpath = ans
    with open(outpath, 'w') as f:
        f.write(MSYS(cntrl, route, remap, geom, smm).to_file())

if __name__ == '__main__':
    try:
        _main()
    except KeyboardInterrupt:
        print('\nInterrupted. Exiting...')
