# ALTOFS.PY -- Alto file system, used by AFU and others
#   supports both Diablo and Trident disk images

# Bob Sproull  4/2018   rfsproull@gmail.com

#
import os,sys,string

# Printing done in a way that works in Pythons 2 and 3
def pr(s, no_cr=False):
    """ Print string s, flush. Append crlf unless last char of s is _ """
    # written to be oblivious to Python 2.7 <=> Python 3 issues
    #print "PR: ",'|'+s+'|',no_cr
    if len(s) > 0 and s[-1:] == '_':
        sys.stdout.write(s[:-1])     # to be continued
    elif no_cr:
        sys.stdout.write(s)
    else:
        sys.stdout.write(s)
        sys.stdout.write('\n')       # put in crlf
    sys.stdout.flush()

# Print a sequence of items, using str, with spaces between each
def prr(*args):
    """Print arguments using str(*), append crlf unless last char is _ """
    for i in range(len(args)):
        s = str(args[i])
        pr(s, True)
        no_cr = len(s) > 0 and (s[-1] == '_')
        if i != len(args)-1:
            pr(" ", True)
        else:
            if not no_cr: pr("")

# Convert a byte array to a string
def str_ba(ba, max_len=None):
    s = "["+str(len(ba))+":"
    prn = len(ba) if max_len is None else max_len
    for i in range(prn):
        s += str(ba[i])
        if i != prn-1: s += ","
    return s+"]"

# Convert a number to octal
def str_o(n):
    return format(n, "#o")

# strstr -- recursively applies "str" to return a print string
def strstr(v):
    if not hasattr(v, '__iter__'): return str(v)
    if type(v) == type({}):
        s = "{"
        for key in v:
            s += str(key) + ": " + strstr(v[key]) + ";;; "
        s += "}"
    else:
        s = "["
        for e in v: s += strstr(e) + " "
        s += "]"
    return s

# ASCII interpretation of word or spaces if not in ASCII range
def word_to_chars(n):
    b1 = (n >> 8) & 0o377
    b2 = n & 0o377
    b1s = " "
    if is_char_ASCII(b1):
        b1s = chr(b1)
    b2s = " "
    if is_char_ASCII(b2):
        b2s = chr(b2)
    return b1s + b2s

# Predicate to decide whether byte is a "printable" ASCII character
def is_char_ASCII(n):
    return n >= 0o40 and n < 0o177

# Collect a BCPL string; 'get_word' is a lambda usually
def get_BCPL_string(get_w):
    s = ""
    slen = get_w(0) >> 8
    for ci in range(slen):
        w = get_w((ci+1)//2)
        c = get_byte(w, ci ^ 1)
        s += chr(c)
    return s

# Store a BCPL string at a given (word) spot
def set_BCPL_string(put_w, s):
    w = len(s) << 8
    for ci in range(len(s)):
        ch = ord(s[ci])
        if (ci & 1) == 0:
            w += ch
        else:
            w = ch << 8
        put_w((ci+1)//2, w)

# get left (idx even) or right (idx odd byte)
def get_byte(wd, idx):
    if (idx & 1) == 0:
        return wd >> 8
    return wd & 0o377
    

## ********************************************************************************************************
##               CONSTANTS
## ********************************************************************************************************

# TEXT FILE CONVENTIONS

MINUS_ONE = 0o177777  # 16-bit all ones

# End of line conventions:
#    Alto = CR = \r
#    Unix,Mac = LF = \n
#    Windows = CRLF = \r\n

# can use os.sep to determine which kind of system you're on (/ or \)
# or can use platform.system = "Windows" or "Darwin"...

CR = 0o15
LF = 0o12

# File types are:
#   Auto = figure it out by looking at file
#   Binary
#   Text (platform text type)
#   Text-CR
#   Text-LF
#   Text-CRLF

def get_host_text_type():
    return ('Text-CRLF' if os.sep =="\\" else 'Text-LF')


LEADER_ADJUST = 1        # used in calculations that adjust for leader in file (e.g., numChars)

DSK_FILE_SEC_HEADER = 1  # document 1 word of header in .dsk files for each sector
VDA_FIX = True           # Trident sector permutation bug



## ********************************************************************************************************
##        CLASS INDEXED_IO
## ********************************************************************************************************

# Routines for reading/writing words/bytes from buffers, either disk sectors or file blocks
# This is really a way to overload "get_word" and "set_word" in order to retain those names.
# It's a bit of a hack to make one set of routines work for both, depending on the calling sequence:
#  If "vda" is provided, it's the vda of a disk sector that should be accessed
#       idx is offset by DH_base, DL_base, or 0 (for data) to read separate blocks
#  If no vda, it's a file with a file_vdas[] list to obtain the vda of a disk sector
#       idx may be offset by disk.LD_offset = -disk.DD_len to reference leader page
#       idx >= 0 is an index to a data word in the file
#       for byte access, the offset is twice that

# The caller object must contain one or both of the following attributes:
#  disk              -- to read/write disk sector data
#  file_vdas[]       -- indexed by page number in file (0 = leader page) to find vda of that block
#                           caller must also have disk attribute to find sector data
#  file_len_w        -- length of file in words
#  file_len_b        -- length of file in bytes

# BEWARE that .dsk files are byte-swapped !!!!!!!

class Indexed_IO:

    def get_word(self, idx, vda=None):
        disk = self.disk
        if vda is not None:
            # Read from disk sector
            ba = disk._get_ba(vda)
            return self._get_word_from_bytes(ba, idx + disk.index_offset)
        # Read from file
        ba = disk._get_ba(self.file_vdas[(idx // disk.DD_len) + LEADER_ADJUST])
        return self._get_word_from_bytes(ba, (idx % disk.DD_len) + disk.index_offset)

    def set_word(self, idx, w, vda=None):
        disk = self.disk
        if vda is not None:
            # Write into disk sector
            ba = disk._get_ba(vda, True)
            self._set_bytes_from_word(ba, idx + disk.index_offset, w)
        else:
            # Write into file
            ba = disk._get_ba(self.file_vdas[(idx // disk.DD_len) + LEADER_ADJUST], True)
            self._set_bytes_from_word(ba, (idx % disk.DD_len) + disk.index_offset, w)

    # works only for data bytes (not header or label, but works for leader data)
    def get_byte(self, idx, vda=None):
        w = self.get_word(idx // 2, vda)
        if (idx & 1) == 0: w = w >> 8
        return w & 0o377

    def set_byte(self, idx, b, vda=None):
        w = self.get_word(idx // 2, vda)
        if (idx & 1) == 0:
            w = (w & 0o377) + (b << 8)
        else:
            w = (w & 0o177400) + (b & 0o377)
        self.set_word(idx // 2, w, vda)

    # define conversion from bytes read from file to words
    # disk-image files (.dsk) are byte-swapped compared to binary files in big-endian order
    def _get_word_from_bytes(self, ba, word_idx):
        ci = word_idx*2
        return (ba[ci+1] << 8) + ba[ci] # byte-swap

    # inverse of _word_from_bytes
    def _set_bytes_from_word(self, ba, word_idx, w):
        ci = word_idx*2
        ba[ci]   = w & 0o377 # byte-swap
        ba[ci+1] = w >> 8    # byte-swap

## ********************************************************************************************************
##        CLASS DISK
## ********************************************************************************************************

class Disk (Indexed_IO):
    """A disk is a collection of sectors (header, label, data blocks) with
    methods for reading and writing the sectors.
    A disk is storage for a single file system.  If there are two drives that
    function like one disk, they are treated as one disk object."""

    # Select a disk based on the size of the .dsk file
    @classmethod
    def select(cls, fullfilename):
        word_len = os.path.getsize(fullfilename)//2
        ext = os.path.splitext(fullfilename)[1].lower()
        if Diablo.is_file_right(ext, word_len):
            return Diablo(fullfilename)
        if Trident.is_file_right(ext, word_len):
            return Trident(fullfilename)
        return None

    # Attributes that subclasses must have
    # nSectors, nHeads, nCylinders, nDrives
    # DH_len, DL_len, DD_len (length of header, label, data blocks in words)

    def __init__(self, fullfilename):
        self.disk = self   # so Indexec_IO can find us
        self.fullfilename = fullfilename
        self.dirty = False    # not written yet

        # total sector length
        self.DBLK_len = self.DH_len + self.DL_len + self.DD_len
        # get_word: word offsets in bytearray to get to appropriate block
        self.DH_base = - self.DL_len - self.DH_len
        self.DL_base = - self.DL_len
        self.index_offset = - self.DH_base + DSK_FILE_SEC_HEADER  # offset in bytearray to find data block

        # These are defined dynamically because they depend on disk properties
        self.LD_offset = -self.DD_len
        self.LD_name = self.LD_offset + 6
        self.LD_property = self.LD_offset + 246  # beginning index, length
        self.LD_bits = self.LD_offset + 247   # consecutive hint is sign bit
        self.LD_dirFp = self.LD_offset + 248
        self.LD_hintLastPageFa = self.LD_offset + 253

    def is_file_size_right(self):
        file_word_len = os.path.getsize(self.fullfilename)//2
        file_sec_count = file_word_len // (self.DBLK_len + DSK_FILE_SEC_HEADER)
        self.nVDAs = self.nDisks * self.nTracks * self.nHeads * self.nSectors
        return file_sec_count == self.nVDAs

    # Create print-string of a part of a sector
    def _str_block(self, vda, idx, cnt):
        s = ""
        for i in range(cnt):
            s += str_o(self.get_word(idx + i, vda=vda)) + " "
        return s

    # Print out a summary of a disk "sector"
    def print_sector(self, vda):
        s = "Sector vda = "+str(vda)
        if True: # print header
            s += " Header: "+self._str_block(vda, self.DH_base, self.DH_len)+"\n"
        if True: # print label
            s += " Label: "+self._str_block(vda, self.DL_base, self.DL_len)+"\n"
        if True: # print first 20 words
            so = "Octal "
            sc = "Chars |"
            for i in range(20):
                so += str_o(self.get_word(i, vda=vda))+" "
                sc += word_to_chars(self.get_word(i, vda=vda))
            s += so + "\n" + sc + "|\n"
        # Actually print it
        pr(s)

    def vda_verify(self, vda):
        da = self.VDA_to_DA(vda)
        prr("VDA verify: ",vda,"=> ",da,strstr(da))
        vda = self.DA_to_VDA(da)
        prr("   and backL :",vda)

class Diablo(Disk):

    @classmethod
    def is_file_right(cls, ext, word_len):
        if ext != '.dsk': return False
        sec_len = 2 + 8 + 256 + DSK_FILE_SEC_HEADER     # see below for same disk config
        if word_len % sec_len != 0: return False
        nTracks = word_len // (sec_len * 12 * 2)
        if nTracks == 203 or nTracks == 406 or nTracks == 812: return True
        return False

    def __init__(self, fullfilename):

        # Sector size parameters
        self.DH_len = 2
        self.DL_len = 8
        self.DD_len = 256

        self.nSectors = 12
        self.nHeads = 2
        self.nTracks = 203   # may be changed -- see below
        self.nDisks = 1      # may be changed

        # This call is placed here in order to compute other disk attributes
        Disk.__init__(self, fullfilename)
        self.fullfilename2 = None   # one-disk system

        # word offsets and lengths in DL
        self.DL_next = self.DL_base + 0
        self.DL_previous = self.DL_base + 1
        self.DL_numChars = self.DL_base + 3
        self.DL_pageNumber = self.DL_base + 4
        self.DL_FID_version = self.DL_base + 5
        self.DL_FID_SN = self.DL_base + 6

        self.DL_next_len = 1

        # word offsets in DiskDescriptor
        self.KDH_bitTable = 16

        for config in ((1,203), (2,203), (1,406), (2,406), -1):
            if config == -1:
                raise Exception("File size not right for Diablo disk configurations.")
            self.nDisks = config[0]
            self.nTracks = config[1]
            if self.is_file_size_right(): break

        # Note: nDisks may not be right -- DiskDescriptor may call for 2 disks
        # even though file records only one

        self.sectors = []  # holds bytearray for the sectors of the disk
        dsk_fil = open(self.fullfilename, "rb")
        for i in range(self.nVDAs):
            contents = bytearray(dsk_fil.read((self.DBLK_len + DSK_FILE_SEC_HEADER)*2))
            self.sectors.append(contents)

        #prr("Final disk shape: nDisks",self.nDisks,"nTracks",self.nTracks,"nHeads",self.nHeads,"nSectors",self.nSectors)

    # Disk descriptor discovered that it says 2 disks; so read another one
    def add_second_drive(self):
        # look for and replace the last "0" in the name with "1"
        parts = self.fullfilename.rpartition("0")
        if parts[1] != "0":
            raise Exception("For a 2-disk system, file name must have a '0' in it.")
        self.fullfilename2 = parts[0] + "1" + parts[2]
        # read in the same number of VDAs as for the first disk
        prr("Reading",self.fullfilename2,"to form a 2-disk file system.")
        dsk_fil = open(self.fullfilename2, "rb")
        for i in range(self.nVDAs):
            contents = bytearray(dsk_fil.read((self.DBLK_len + DSK_FILE_SEC_HEADER)*2))
            self.sectors.append(contents)
        # and bump the number of vdas
        self.nVDAs *= 2
        self.nDisks = 2

        # DEBUG
        #disk.print_sector(self.nVDAs//2)
        #disk.print_sector((self.nVDAs//2)+1)

    # Write out current disk as a new disk image
    def write_disk(self):
        if not self.dirty: return
        write_nVDAs = self.nVDAs
        if self.fullfilename2 is not None: write_nVDAs = self.nVDAs//2
        # write first disk
        with open(self.fullfilename, "wb") as f:
            for vda in range(write_nVDAs):
                f.write(self.sectors[vda])
            f.close()
        if self.fullfilename2 is None: return
        # write second disk
        with open(self.fullfilename2, "wb") as f:
            for vda in range(write_nVDAs):
                f.write(self.sectors[vda + write_nVDAs])
            f.close()

    def get_sec_property(self, vda, prop_name):
        offset = {'next': self.DL_next, 'numChars': self.DL_numChars, 'pageNumber': self.DL_pageNumber, 'FID': 2000}[prop_name]
        if offset < 2000: return self.get_word(offset, vda=vda)
        # multi-word entries
        # FID
        return (self.get_word(self.DL_FID_version, vda=vda),
                self.get_word(self.DL_FID_SN, vda=vda),
                self.get_word(self.DL_FID_SN+1, vda=vda))

    def _get_ba(self, vda, dirty=False):
        if dirty: self.dirty = True
        return self.sectors[vda]

    # Convert VDA to DA
    def VDA_to_DA(self, vda):
        sector = vda % self.nSectors
        vda = vda // self.nSectors
        head = vda % self.nHeads
        vda = vda // self.nHeads
        track = vda % self.nTracks
        disk = vda // self.nTracks
        if disk > self.nDisks:
            raise Exception("Bad virtual disk address")
        # Now put in single-word format used by Alto hardware
        return (sector << 12) + (track << 3) + (head << 2) + (disk << 1)

    # Convert DA to VDA
    def DA_to_VDA(self, da):
        sector = (da >> 12) & 0o17
        track = (da >> 3) & 0o777
        head = (da >> 2) & 0o1
        disk = (da >> 1) & 0o1
        if sector >= self.nSectors or track >= self.nTracks or head >= self.nHeads or disk >= self.nDisks:
            raise Exception("Bad physical disk address")
        return ((disk * self.nTracks + track) * self.nHeads + head) * self.nSectors + sector

    # Disk knows shape of DA
    def get_DA(self, idx, vda):
        return self.get_word(idx, vda=vda)

    def set_DA(self, idx, da, vda):
        self.set_word(idx, da, vda=vda)

class Trident(Disk):

    @classmethod
    def is_file_right(cls, ext, word_len):
        if ext != '.dsk80': return False
        sec_len = 2 + 10 + 1024 + DSK_FILE_SEC_HEADER     # see below for same disk config
        if word_len % sec_len != 0: return False
        nHeads = word_len // (sec_len * 9 * 815)
        if nHeads == 5: return True                       # code does not handle T300
        return False

    def __init__(self, fullfilename):

        # Sector size parameters
        self.DH_len = 2
        self.DL_len = 10
        self.DD_len = 1024

        self.nSectors = 9
        self.nHeads = 5      # T300 has 19 heads
        self.nTracks = 815
        self.nDisks = 1

        # This call is placed here in order to compute other disk attributes
        Disk.__init__(self, fullfilename)

        # word offsets and lengths in DL
        self.DL_next = self.DL_base + 8
        self.DL_previous = self.DL_base + 6
        self.DL_numChars = self.DL_base + 4
        self.DL_pageNumber = self.DL_base + 5
        # FID in different order in TFS than BFS -- undocumented difference
        self.DL_FID_version = self.DL_base + 2
        self.DL_FID_SN = self.DL_base + 0

        self.DL_next_len = 2

        # word offsets in DiskDescriptor
        self.KDH_bitTable = 1024

        for config in (5, 19, -1):
            if config == -1:
                raise Exception("File size not right for Diablo disk configurations.")
            self.nHeads = config
            if self.is_file_size_right(): break

        self.dsk_fil = open(self.fullfilename, "r+b")  # read,write
        self.vda_in_buffer = -1
        self.vda_dirty = False

        #prr("Final disk shape: nDisks",self.nDisks,"nTracks",self.nTracks,"nHeads",self.nHeads,"nSectors",self.nSectors)

    # No way to add second drive; disk descriptor code will raise exception
    def add_second_drive(self):
        pass

    def write_disk(self):
        # make sure any buffered writes are done
        self._get_in_buffer(0)
        self._get_in_buffer(1)
        self.dsk_fil.close()

    def get_sec_property(self, vda, prop_name):
        offset = {'next': 2000, 'numChars': self.DL_numChars, 'pageNumber': self.DL_pageNumber, 'FID': 2001}[prop_name]
        if offset < 2000: return self.get_word(offset, vda=vda)
        # multi-word entries
        # FID
        if offset == 2000:  # next DA -- 2 words
            return (self.get_word(self.DL_next, vda=vda),
                    self.get_word(self.DL_next+1, vda=vda))
        # FID
        return (self.get_word(self.DL_FID_version, vda=vda),
                self.get_word(self.DL_FID_SN, vda=vda),
                self.get_word(self.DL_FID_SN+1, vda=vda))

    def _position_file_at_vda(self, vda):
        if VDA_FIX:
            but_sec = vda // 9
            sec = (vda+1) % 9   # permute sectors
            vda = (but_sec*9) + sec
        pos = vda * (self.DBLK_len + DSK_FILE_SEC_HEADER)
        self.dsk_fil.seek(pos*2)

    def _get_in_buffer(self, vda):
        if self.vda_dirty:
            self._position_file_at_vda(self.vda_in_buffer)
            self.dsk_fil.write(self.vda_buffer)
        self._position_file_at_vda(vda)
        self.vda_buffer = bytearray(self.dsk_fil.read((self.DBLK_len + DSK_FILE_SEC_HEADER)*2))
        self.vda_in_buffer = vda
        self.vda_dirty = False
        # check to see if things are right
        #self.print_sector(vda)
        if VDA_FIX:
            # get header from block just read
            da = (self.get_word(self.DH_base, vda=vda),
                  self.get_word(self.DH_base+1, vda=vda))
            vda_read = self.DA_to_VDA(da)
            if vda_read != vda:
                self.print_sector(vda)
                raise Exception("_get_in_buffer got wrong data "+str(da)+" "+str(vda))

    def _get_ba(self, vda, dirty=False):
        if vda != self.vda_in_buffer: self._get_in_buffer(vda)
        if dirty:
            self.vda_dirty = True
            self.dirty = True
        return self.vda_buffer

    # Convert VDA to DA
    def VDA_to_DA(self, vda):
        sector = vda % self.nSectors
        vda = vda // self.nSectors
        head = vda % self.nHeads
        vda = vda // self.nHeads
        track = vda
        if track >= self.nTracks:
            raise Exception("Bad virtual disk address")
        # Now put in two-word format used by TFS
        return ( track, (head << 8) + sector)

    # Convert DA to VDA
    def DA_to_VDA(self, da):
        sector = da[1] & 0o377
        head = da[1] >> 8
        track = da[0]
        if sector >= self.nSectors or track >= self.nTracks or head >= self.nHeads:
            raise Exception("Bad physical disk address")
        return ((track * self.nHeads) + head) * self.nSectors + sector

    # Disk knows shape of DA
    def get_DA(self, idx, vda):
        return (self.get_word(idx, vda=vda), self.get_word(idx+1, vda=vda))

    def set_DA(self, idx, da, vda):
        self.set_word(idx, da[0], vda=vda)
        self.set_word(idx+1, da[1], vda=vda)

## ********************************************************************************************************
##        CLASS FILESYSTEM
## ********************************************************************************************************

# KDH -- disk descriptor, in AltoFileSys.d
KDH_nDisks = 0
KDH_nTracks = 1
KDH_nHeads = 2
KDH_nSectors = 3
KDH_lastSn = 4        # last file serial number issued
KDH_diskBTsize = 7    # number of words in bit table
KDH_freePages = 9

# Trident stuff
KDH_VDAdiskDD = 19    # beginning of list of VDAs for bit table
KDH_firstVTrack = 20  # first track used in file system
KDH_nVTracks = 21     # number of tracks used in file system

class FileSystem (Indexed_IO):
    """A file system is a collection of files, stored on a disk.  The file system
    includes special files: DiskDescriptor, SysDir.

    The file system contains routines to read, write, create and delete files
    with sector-level access.   Also routines to manipulate disk directory,
    file directory (SysDir).
    """
    # Not a subclass of class disk, but has a pointer to the disk that implements the FS

    # Init sets up directory, disk descriptor only on main call, not inits from subclasses

    def __init__(self, disk):
        self.disk = disk

        # A file system has a disk descriptor and a directory, both opened as files and updated in place
        self.directory = Directory(1, self)
        #prr("Directory", self.directory)
        self.disk_descriptor = DiskDescriptor(self)
        #prr("Disk descriptor", self.disk_descriptor)
        # Not all disks will have Swatee; will be None if non-existent
        #self.swatee = self.file("Swatee.")
        #prr("Swatee", self.swatee)

    def fsck(self):
        pass

# Things to check
# look for all leader pages (save vda, leadername, serial number)
# make sure there's a SysDir. and a DiskDescriptor.
# vda=0 is boot record, which is usually just a copy of some other page
# make sure all serial numbers are unique
# then enumerate all files, check each file for valid:
#     next/previous links
#     numChars = self.DD_len*2 on all but last page
#     serial numbers the same on all labels
#     make each page as in use
# read DiskDescriptor
#     make sure all pages in use are so marked
#     make sure next serial number is above all in use

# Wrapper for File(...) that can return None if no file found
    def file(self, name_or_leader):
        f = File(name_or_leader, self)
        if f.leader_vda == -1: return None
        return f

# Create a new file with given total length, return File object
# data_length is in bytes
# Note that last page must have numChars != DD_len*2

    def create_file(self, nam, data_length):
        #prr("Create file", nam, data_length)
        # make sure there's a trailing .
        if nam[-1:] != '.': nam += '.'
        disk = self.disk
        data_block_len = disk.DD_len*2   # bytes
        numChars = data_length + data_block_len * LEADER_ADJUST # includes file and leader page

        # first, allocate pages and write their new labels
        self.file_vdas = []
        for i in range((numChars + data_block_len) // data_block_len):  # number of pages
            self.file_vdas.append(self.disk_descriptor.allocate_page())
        # from here on, get_word and set_word see us as a "file" because self.file_vdas is valid
        # increment file serial number
        self.disk_descriptor.set_word(KDH_lastSn+1, self.disk_descriptor.get_word(KDH_lastSn+1) + 1) # ignore first word
        # now need to check and write labels appropriately
        for i in range(len(self.file_vdas)):
            vda = self.file_vdas[i]
            # check fileID to be sure it's correct for deleted page
            fid = disk.get_sec_property(vda, 'FID')
            if fid != (MINUS_ONE, MINUS_ONE, MINUS_ONE):
                prr("Deleted page has bad fileID", vda, fid)

            first = (i == 0)
            last = (i == len(self.file_vdas)-1)
            # zero data for leader page and to avoid confusion on other pages
            for j in range(disk.DD_len): self.set_word(j, 0, vda=vda)
            # need to put some stuff in leader page
            if first:
                # Writing in leader page depends on file_vdas access by BuffIO:set_word
                set_BCPL_string(lambda i,w: self.set_word(disk.LD_name+i, w), nam)
                self.set_word(disk.LD_property, (26 << 8) + 210)  # all decimal numbers in this line
                self.set_word(disk.LD_hintLastPageFa, self.file_vdas[len(self.file_vdas)-1])  # vda of last page
                self.set_word(disk.LD_hintLastPageFa +1, len(self.file_vdas)-1)      # number of last page (leader = 0)
                self.set_word(disk.LD_hintLastPageFa +2, numChars % (disk.DD_len*2))    # numChars on last page (always < DD_len*2)
                #prr("Creating leader page for",nam); disk.print_sector(vda)

            da_zero = disk.VDA_to_DA(0)
            disk.set_DA(disk.DL_next, da_zero if last else disk.VDA_to_DA(self.file_vdas[i+1]), vda)
            disk.set_DA(disk.DL_previous, da_zero if first else disk.VDA_to_DA(self.file_vdas[i-1]), vda)
            # last page will never have numChars = 512 -- this is not a legal Alto file
            self.set_word(disk.DL_numChars, disk.DD_len*2 if not last else numChars-(len(self.file_vdas)-1)*disk.DD_len*2, vda)
            self.set_word(disk.DL_pageNumber, i, vda)
            self.set_word(disk.DL_FID_version, 1, vda)  # version
            self.set_word(disk.DL_FID_SN, self.disk_descriptor.get_word(KDH_lastSn), vda)
            self.set_word(disk.DL_FID_SN+1, self.disk_descriptor.get_word(KDH_lastSn + 1), vda)

        FP = [self.disk_descriptor.get_word(KDH_lastSn), self.disk_descriptor.get_word(KDH_lastSn+1), 1, 0, self.file_vdas[0]]
        self.directory.add(nam, FP)
        # return leader_vda
        return self.file_vdas[0]

    # returns True if file existed and was deleted
    def delete_file(self, nam):
        # insure trailing .
        if nam[-1:] != '.': nam += '.'
        f = File(nam, self)
        if not f.exists(): return False
        #prr("Deleting file",nam,"vdas",f.file_vdas)
        # found file
        for p in f.file_vdas:
            self.disk_descriptor.free_page(p)
            # write label with FID set to -1
            disk = self.disk
            for i in range(disk.DL_base, disk.DL_base + disk.DL_len):
                w = 0
                if i in (disk.DL_FID_version, disk.DL_FID_SN, disk.DL_FID_SN+1): w = MINUS_ONE
                self.set_word(i, w, vda=p)
        # remove entry from directory
        self.directory.remove(nam)
        return True

## ********************************************************************************************************
##        CLASS FILE
## ********************************************************************************************************

class File (FileSystem):
    """Create a File object to operate on a file; this does not create the file
    in the file system.  You can tell if the file is good by testing leader_vda != -1
    """

    def __init__(self, leader_vda, file_system):
        """Create file object: different wants to call
        leader_vda = vda of leader page
        leader_vda = string name of file ("" to create empty file object)
        """

        self.disk = file_system.disk   # be sure you can find the real disk data
        self.leader_name = "*unknown*"
        # if argument is string, look it up in directory
        if isinstance(leader_vda, type("a")):   # if argument is a string
            # insure trailing .
            if leader_vda[-1:] != '.': leader_vda += '.'
            self.lookup_name = leader_vda
            dir_find = file_system.directory.lookup(leader_vda)
            #prr("Lookup",self.lookup_name,"leader_vda",dir_find)
            if dir_find is None:
                leader_vda = -1  # no file 
            else:
                leader_vda = dir_find['leader_vda']
        # fall through if vda is the vda number of leader page
        self.leader_vda = leader_vda
        if leader_vda != -1:
            self._index_file()    # fill in the rest of the properties

    # Index the file, filling instance variables leader_name, length, file_vdas
    def _index_file(self):
        disk = self.disk
        vda = self.leader_vda
        self.file_vdas = [ vda ]
        numChars = 0  # total chars in file, counting leader
        while True:
            if vda == self.leader_vda: # leader page
                self.leader_name = get_BCPL_string(lambda i: self.get_word(disk.LD_name+i))
            #prr("Indexing file"); disk.print_sector(vda)
            nx = self.disk.DA_to_VDA(disk.get_DA(disk.DL_next, vda))
            numChars += self.get_word(disk.DL_numChars, vda)
            if nx == 0: break
            if self.get_word(disk.DL_numChars, vda) != disk.DD_len*2:
                prr("_index_file: numChars must be",disk.DD_len*2,"on non-terminal page")
            self.file_vdas.append(nx)
            vda = nx
        # report file length WITHOUT leader page
        self.length = numChars - disk.DD_len*2*LEADER_ADJUST

    # determine whether file exists (e.g., after a lookup)
    def exists(self):
        return self.leader_vda != -1

    # return (text) string for entire file
    def read_as_string(self):
        for ci in range(self.length):  # to numChars
            ch = self.get_byte(ci)
            # Convert CR to LF to match Python
            if ch == CR: ch = LF
            s += chr(ch)
        return s

    def __str__(self):
        s = "File: "
        s += self.leader_name
        if hasattr(self, 'file_vdas'):
            s += " file_vdas" + str(self.file_vdas)
        else:
            s += " [no vdas -- file does not exist]"
        return s

## ********************************************************************************************************
##        CLASS DISK DESCRIPTOR
## ********************************************************************************************************

class DiskDescriptor (File):

    def __init__(self, file_system):
        File.__init__(self, "DiskDescriptor.", file_system)
        if self.leader_vda == -1: raise Exception("Cannot find DiskDescriptor.")
        disk = self.disk
        trouble = False
        n_disks = self.get_word(KDH_nDisks)
        if n_disks == 2:
            # This is the first time we see that there may be 2 disks in a single FS
            # If disk can add a second system, it will show up in disk.nDisks
            disk.add_second_drive()
        if n_disks != disk.nDisks: trouble = True
        if self.get_word(KDH_nTracks) != disk.nTracks: trouble = True
        if self.get_word(KDH_nHeads) != disk.nHeads: trouble = True
        if self.get_word(KDH_nSectors) != disk.nSectors: trouble = True
        if trouble:
            s = ""
            for i in range(KDH_nDisks, KDH_nSectors+1): s += str(self.get_word(i))+" "
            raise Exception("DiskDescriptor format does not match config: "+s)
        # update to disk descriptor trugh
        self.nVDAs = disk.nDisks * disk.nTracks * disk.nHeads * disk.nSectors
        # check free page count, update if wrong
        free_c = 0
        # Check that bit table and free count agree
        for vda in range(self.nVDAs):
            if self.is_page_free(vda): free_c += 1
        if free_c != self.get_word(KDH_freePages):
            self.set_word(KDH_freePages, free_c)
            prr("DiskDescriptor free page count updated to", free_c)

    # determine status of a page
    def is_page_free(self, vda):
        w = vda // 16
        b = vda % 16
        r = self.get_word(self.disk.KDH_bitTable + w) & (0o100000 >> b)
        return (r == 0)

    # set bit for page (1=used, 0=free)
    def set_page_bit(self, vda, bit_val, free_count_increment):
        w = vda // 16
        b = vda % 16
        v = self.get_word(self.disk.KDH_bitTable + w)
        if bit_val == 0:
            v &= ~(0o100000 >> b)
        else:
            v |=  (0o100000 >> b)
        self.set_word(self.disk.KDH_bitTable + w, v)
        self.set_word(KDH_freePages, self.get_word(KDH_freePages) + free_count_increment)
        
    # find a free page, mark it in use, return vda
    def allocate_page(self):
        for vda in range(self.nVDAs):
            if self.is_page_free(vda):
                self.set_page_bit(vda, 1, -1)
                return vda
        raise Exception("Cannot allocate new page")

    # mark a page free
    def free_page(self, vda):
        self.set_page_bit(vda, 0, 1)




## ********************************************************************************************************
##        CLASS DIRECTORY
## ********************************************************************************************************

DIR_ENTRY_FILE = 1
DIR_ENTRY_FREE = 0

class Directory (File):
    # Although the Alto file system could have subdirectories, they were never used.
    # So this code is written for one directory, but with minor modifications could
    # service multiple directories.

    # SysDir. has a leader_vda = 1

    # All "names" passed to these directory routines must have a "." at the
    # end of the file name.

    def __init__(self, leader_vda, file_system):
        File.__init__(self, leader_vda, file_system)
        if self.leader_vda == -1:
            raise Exception("File system has no SysDir.")
        self.name = "SysDir."
	
    # Directory -- examine DV beginning at word i and return length of block or -1 if EOF
    def _dir_entry_length(self, i):
        if i >= self.length // 2: return -1   # end of file
        h = self.get_word(i)
        return h & 0o1777

    def _dir_entry_type(self, i):
        h = self.get_word(i)
        return h >> 10

    def _dir_entry_set(self, i, typ, length):
        self.set_word(i, (typ << 10) + length)

    # Find directory entry for nam, return index in directory or -1 if not found
    # @todo should be an iterator; then enumerating all files would be easy
    def _dir_entry_search(self, nam):
        idx = 0
        while True:
            length = self._dir_entry_length(idx)
            if length == -1 or length == 0: break   # end of file
            if self._dir_entry_type(idx) == DIR_ENTRY_FILE:   # an occupied entry
                s = get_BCPL_string(lambda i: self.get_word(idx+6+i))
                #prr("Directory entry for",s)
                if s.lower() == nam.lower(): return idx
            idx += self._dir_entry_length(idx)
        return -1

    # Extract info from directory entry at idx
    # Returns dict: name, leader_vda, [FP]
    def _dir_entry_extract(self, idx, returnFP=False):
        # check for empty entry
        if self._dir_entry_type(idx) == DIR_ENTRY_FREE: return None
        vda = self.get_word(idx+5)
        nam = get_BCPL_string(lambda i: self.get_word(idx+6+i))
        result = {'name':nam, 'leader_vda': vda}
        if returnFP:
            fp = []
            for j in range(1,6): fp.append(self.get_word(idx+j))
            fp[3] = 0  # unused, but normal convention is that it's zero
            result['FP'] = fp
        return result

    # Find a particular file in the directory
    # returns None if file not found
    def lookup(self, nam, returnFP=False):
        idx = self._dir_entry_search(nam)
        if idx == -1: return None
        return self._dir_entry_extract(idx, returnFP)

    # Remove an entry in the directory
    def remove(self, nam):
        idx = self._dir_entry_search(nam)
        if idx == -1: return False  # not found
        # fix type, length
        this_len = self._dir_entry_length(idx)
        nxt_idx = idx+this_len
        nxt_len = self._dir_entry_length(nxt_idx)
        # check next entry free and total length not too large
        if nxt_len != -1 and self._dir_entry_type(nxt_idx) == DIR_ENTRY_FREE and this_len+nxt_len < 1000:
            # combine 2 free blocks
            this_len += nxt_len
        # set type = 0 (free), length
        self._dir_entry_set(idx, DIR_ENTRY_FREE, this_len)
        return True

    # Add a file to the directory
    def add(self, nam, FP):
        lenNeeded = 1 + len(FP) + (len(nam)+2) // 2
        idx = 0
        while True:
            oldLen = self._dir_entry_length(idx)
            if oldLen == -1 or oldLen == 0: break  # EOF
            if self._dir_entry_type(idx) == DIR_ENTRY_FREE and oldLen >= lenNeeded:  # it's free and big enough
                for i in range(len(FP)):
                    self.set_word(idx+1+i, FP[i])
                # now store BPCL string
                set_BCPL_string(lambda i,w:self.set_word(idx+1+len(FP)+i, w), nam)
                newLen = oldLen - lenNeeded
                #prr("Lengths ",oldLen,lenNeeded,newLen)
                if newLen < 10:
                    # use entire entry for us
                    self._dir_entry_set(idx, DIR_ENTRY_FILE, oldLen)
                else:
                    self._dir_entry_set(idx, DIR_ENTRY_FILE, lenNeeded)
                    self._dir_entry_set(idx+lenNeeded, DIR_ENTRY_FREE, newLen)
                return  # did the deed
            # end of if free
            idx += oldLen
        raise Exception("Cannot find free directory entry")
            
    # Parse an entire Alto disk directory
    def list(self, returnFP=False):
        files = []
        idx = 0
        while True:
            length = self._dir_entry_length(idx)
            if length == -1 or length == 0: break  # EOF
            e = self._dir_entry_extract(idx, returnFP)
            if e is not None:
                files.append(e)
            idx += self._dir_entry_length(idx)
        return files

