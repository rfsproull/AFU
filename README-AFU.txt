AFU -- Alto File Utility
README-AFU.txt

Bob Sproull   rfsproull@gmail.com      March 2018

AFU is a Python utility for transfering files between a host computer
such as a PC or Mac and a file that is a "disk image" of a disk for
use by an Alto, either a real Alto or the Contralto simulator.  The
name of the utility is deliberately akin to TFU, the Trident disk
utility (an Alto program), but the two utilities differ significantly.

AFU operates on disk images and offers the following sorts of utilities:
    - list the number of free disk pages
    - list the directory
    - delete a file
    - copy a file from host to "Alto" or reverse
    - extract a screen image from Swatee

Because AFU is a command-line program, you can easly build scripts on
the host computer to manipulate Alto disk images.  If you need to
include steps that must be executed on an Alto (e.g., TFU), these can
be handled by using Contralto scripts.

AFU COMMANDS

AFU is a command-line program.  Its command structure is:
    afu [disk-image] [free | ls | directory | screen | help]
    afu [disk-image] delete alto-file*
    afu [disk-image] [type [auto|binary|text-*]]
    	[toalto | fromalto ] file*
    afu [disk-image] [type [auto|binary|text-*]]
    	[toalto-rename | fromalto-rename] alto-file host-file

The optional disk-image argument specifies the name of the disk image file
on which AFU will operate.  AFU detects this option by looking for a
filename with one of the mandatory disk-image filename extensions
(.dsk, .dsk80, .dsk300).  If the disk-image name is omitted, AFU finds
the disk name as follows:
    - Look for an environment variable AFUDSK and use its value
    - Otherwise, use "working.dsk"

The first command format has the following variants:

    free: Prints on standard output the number of free pages on the
        disk image.

    ls: Prints a file directory listing on standard output.

    directory: Same as 'ls', but writes the output to a file named
        <disk-image>.directory.  Thus if the .dsk file name is
        "working.dsk", the output will be "working.dsk.directory".

    screen: Examine the Swatee file to extract the screen image when Swat
        was last invoked, and write out the image on <disk-image>.png

    help: Print out standard output a summary of AFU commands.

Multiple commands of the first format can be on one command line,
e.g. "afu foo.dsk ls free".

The second command format deletes Alto files from the disk image.

The two remaining command formats transfer files between the host
computer (the one running AFU) and the disk image.  Both formats
optionally specify the type of the file:

    Auto: AFU will detect and honor the file type (default)
    Binary: Bytes are transferred without any conversion.
    Text-*: The source file is assumed to be a text file with
        end-of-line (EOL) convention as specified:
        Text-CR       Text file with EOL = carriage return (Alto)
        Text-CRLF     Text file with EOL = CR LF (Windows)
        Text-LF       Text file iwth EOL = LF (Unix, Mac OS)
                      If a conversion is performed, its type is printed.
                      If no conversion is performed, AFU is silent.

The command format without the "rename" option transfers files between
host and Alto using the full names specified on the command line for
both the Alto and host file names.  Full names may contain a host
path, which is ignored on the Alto.  Thus "afu toalto ~/mine/test.txt"
will write an Alto file named "test.txt".  The "name" format allows
the Alto filename and the host filename to differ; NOTE that the Alto
file name always comes first.

ALTO .DSKS

Images of Diablo Model 31 disks, standard for Altos, have been
preserved for use on Altos today; and the Contralto simulator uses
this disk image format as well.  The files are recognizable by their
filename mandatory extensions and file lengths (in bytes):

Disk                  Extension       Length in bytes
Diablo Model 31         .dsk              2601648
Diablo Model 44         .dsk              5203296
Trident T80             .dsk80           76063950
Trident T300            .dsk300         289043010
	(NOTE: AFU does not handle .t300 images)

The Contralto "new" command will make empty disk images (except for
Model 44's); these disk images are "formatted" but do not have file
systems or boot files on them.  To make a file system on a Model 31 or
44 disk, use an Alto program such as "newos" that builds a file system
and installs the operating system.  To make a file system on a Trident
disk image, use the Alto TFU command.

To avoid the tedious business of building a file system, installing
the operating system, and perhaps Swat (and Swatee, its companion), an
easy procedures is to copy an existing .dsk image with these items
already installed, and then delete other files you don't need.  AFU
will do this easily.

MULTI-DRIVE FILE SYSTEMS

The Alto could accommodate two Diable drives, either Model 31 or Model
44.  They could be used in three ways:

     - A single disk in drive 0
     - Two disks, two separate file systems
     - Two disks, ONE filesystem, whose disk metadata (SysDir. and
       DiskDescriptor.) is stored on drive 0.

AFU handles the first two cases by treating the .dsk images
separately, since there is exactly one file system per disk image.

The third case treats two disk image files as a single file system.
AFU, when presented with the disk image for drive 0, detects that the
metadata requires a second disk image.  The name of the second .dsk
file is derived from that of the first by looking for the last "0" in
the filename of the first image, and replacing it with "1".  Thus if
the first disk image is named "big-disk-dp0.dsk", AFU will look for
"big-disk-dp1.dsk" to use for the second image.

TRIDENT T300 IMAGES

AFU does not handle .dsk300 images.  Use the Alto program TFU to work
with these.  TFU will transfer files between .dsk300 and .dsk80
images, which AFU can handle.

IMPLEMENTATIONS NOTES

The implementation of AFU is intended to be simple, not efficient.
Because Alto files are small by today's standards, AFU's speed is
rarely annoying.

The implementation is divided into two parts, altofs.py, a library
that implements Diablo and Trident file systems, and afu, the
file-transfer application.  The library is used for other programs,
e.g., pressbits2ps, which reads portions of a large Trident file
holding a printer page image and creates a Postscript file for viewing
on the host computer.




REFERENCES

Sources of useful .dsk images:
  http://www.bitsavers.org/bits/Xerox/Alto/disk_images/
  https://github.com/livingcomputermuseum/ContrAlto/tree/master/Contralto/Disk

Alto disk format:
  Alto Hardware Manual: http://www.bitsavers.org/pdf/xerox/alto/memos_1979/Alto_Hardware_Manual_May79.pdf
  Alto OS Reference Manual: http://www.bitsavers.org/pdf/xerox/alto/memos_1980/Alto_Operating_System_Reference_Manual_Dec80.pdf
  BCPL definitions and packages:
    http://xeroxalto.computerhistory.org/_cd8_/alto/.altofilesys.d!2.html
    http://xeroxalto.computerhistory.org/_cd8_/alto/.disks.d!2.html
    http://xeroxalto.computerhistory.org/Indigo/AltoSource/BFSSOURCES.DM!4_/.index.html

Trident disk format: @todo
  TFU documentation (includes disk format description):
    Alto Subsystems: http://www.bitsavers.org/pdf/xerox/alto/memos_1981/Alto_Subsystems_May81.pdf
  BPCL definitions and packages:
    http://xeroxalto.computerhistory.org/Indigo/AltoSource/TFSSOURCES.DM!2_/.index.html
