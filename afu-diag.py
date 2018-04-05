#!/usr/bin/env python

# afu-diag.py

from altofs import *

def print_diag(filename):
    f = file_system.file(filename)
    if f is None:
        prr("Cannot find file",filename)
    vdas = f.file_vdas
    prr("File",filename," vdas",vdas)
    if len(vdas) <= 3:
        for i in range(len(vdas)):
            disk.print_sector(vdas[i])
    else:
        disk.print_sector(vdas[0])
        disk.print_sector(vdas[len(vdas)-1])

    

disk = Disk.select("press.dsk80")
file_system = FileSystem(disk)

print_diag("Press.Meter")
print_diag("press.indicate")

