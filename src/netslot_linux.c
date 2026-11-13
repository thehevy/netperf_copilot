/*
#  Copyright 2021 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
# USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

#define _XOPEN_SOURCE 500
#if defined(__linux)
#include <ftw.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static char interface_match[32];
static char interface_address[32];
static char interface_slot[64]="not found";

static int
read_sysfs_string(const char *path, char *buf, size_t buflen)
{
  FILE *f;
  size_t len;

  if (buf == NULL || buflen == 0) return -1;
  buf[0] = '\0';
  f = fopen(path, "r");
  if (f == NULL) return -1;
  if (fgets(buf, (int)buflen, f) == NULL) {
    fclose(f);
    return -1;
  }
  fclose(f);
  len = strlen(buf);
  while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r' || buf[len - 1] == ' ')) {
    buf[--len] = '\0';
  }
  return 0;
}

static int
find_slot(const char *fpath, const struct stat *sb,
	  int tflag, struct FTW *ftwbuf)
{
  char slot_address[11];
  int  ret;
  FILE *address_file;
  char *myfpath;
  char *this_tok;
  char *last_tok = NULL;

  /* so, are we at a point in the tree where the basename is
     "address" ? */
  if (strcmp("address",fpath + ftwbuf->base) == 0) {
    address_file = fopen(fpath,"r");
    if (address_file == NULL) {
      strcpy(interface_slot,"fopen");
      return 0;
    }
    /* we make the simplifying assumption that PCI domain, bus, slot
       and function, with associated separators, are 10 characters or
       less */
    ret = fread(slot_address,1,10,address_file);
    if (ret != 10) {
      strcpy(interface_slot,"fread");
      fclose(address_file);
      return 0;
    }
    slot_address[ret] = 0;
    /* the slot address will be a substring of the full bus address of
       the interface we seek */
    if (strstr(interface_address,slot_address)) {
	myfpath = strdup(fpath);
	if (myfpath == NULL) {
	  strcpy(interface_slot,"strcpy");
	  return 1;
	}

	this_tok = strtok(myfpath,"/");
	while (strcmp(this_tok,"address")) {
	  last_tok = this_tok;
	  this_tok = strtok(NULL,"/");
	}
	if (last_tok != NULL)
	  strncpy(interface_slot,last_tok,sizeof(interface_slot)-1);
	else
	  strcpy(interface_slot,"last_tok");
	interface_slot[sizeof(interface_slot)-1] = '\0';
	free(myfpath);
	fclose(address_file);
	return 1;
    }
    fclose(address_file);
  }
  return 0;
}

static int
find_interface(const char *fpath, const struct stat *sb,
	       int tflag, struct FTW *ftwbuf)
{
  char *myfpath;
  char *this_tok;
  char *last_tok = NULL;

  if (strcmp(interface_match,fpath + ftwbuf->base) == 0) {
    myfpath = strdup(fpath);
    if (myfpath == NULL) {
      strcpy(interface_address,"strcpy");
      return 1;
    }
    this_tok = strtok(myfpath,"/");
    while (strcmp(this_tok,interface_match)) {
      last_tok = this_tok;
      this_tok = strtok(NULL,"/");
    }
    if (last_tok != NULL)
      strncpy(interface_address,last_tok,sizeof(interface_address)-1);
    else
      strcpy(interface_address,"last_tok");
    interface_address[sizeof(interface_address)-1] = '\0';
    free(myfpath);
    return 1;
  }
  return 0;
}

void
find_interface_pcie_info(char *interface_name, int *numa_node, char *link_speed, char *link_width, int len)
{
  char sysfile[160];
  char numabuf[32];

  if (numa_node != NULL) {
    *numa_node = -1;
    snprintf(sysfile, sizeof(sysfile), "/sys/class/net/%s/device/numa_node", interface_name);
    if (read_sysfs_string(sysfile, numabuf, sizeof(numabuf)) == 0) {
      *numa_node = atoi(numabuf);
    }
  }
  if (link_speed != NULL && len > 0) {
    snprintf(sysfile, sizeof(sysfile), "/sys/class/net/%s/device/current_link_speed", interface_name);
    if (read_sysfs_string(sysfile, link_speed, (size_t)len) != 0) {
      strncpy(link_speed, "N/A", (size_t)len);
      link_speed[len - 1] = '\0';
    }
  }
  if (link_width != NULL && len > 0) {
    snprintf(sysfile, sizeof(sysfile), "/sys/class/net/%s/device/current_link_width", interface_name);
    if (read_sysfs_string(sysfile, link_width, (size_t)len) != 0) {
      strncpy(link_width, "N/A", (size_t)len);
      link_width[len - 1] = '\0';
    }
  }
}

char *
find_interface_slot(char *interface_name) {

  int flags = 0;
  int ret;
  int numa_node = -1;
  char link_speed[32];
  char link_width[32];
  char devlink[256];
  char syspath[160];
  ssize_t linklen;

  strcpy(interface_slot, "not found");
  interface_address[0] = '\0';

  /* Resolve PCI BDF directly via /sys/class/net/<if>/device symlink first */
  snprintf(syspath, sizeof(syspath), "/sys/class/net/%s/device", interface_name);
  linklen = readlink(syspath, devlink, sizeof(devlink) - 1);
  if (linklen > 0) {
    char *slash;
    devlink[linklen] = '\0';
    slash = strrchr(devlink, '/');
    if (slash != NULL && *(slash + 1) != '\0') {
      strncpy(interface_address, slash + 1, sizeof(interface_address) - 1);
      interface_address[sizeof(interface_address) - 1] = '\0';
    }
  }

  flags |= FTW_PHYS;  /* don't follow symlinks for they will lead us
			 off the path */
  if (interface_address[0] == '\0') {
    ret = snprintf(interface_match,31,"net:%s",interface_name);
    interface_match[31]=0;
    /* having setup the basename we will be seeking, go find it and the
       corresponding interface_address */
    nftw("/sys/devices", find_interface, 20, flags);
  }
  /* now that we ostensibly have the pci address of the interface
     (interface_address, lets find that slot shall we? */
  nftw("/sys/bus/pci/slots", find_slot, 20, flags);

  /* Modern PCIe 5.0/6.0 servers often have empty /sys/bus/pci/slots;
     fall back to reporting PCIe BDF, NUMA node, link speed, and width. */
  if (strcmp(interface_slot, "not found") == 0 ||
      strcmp(interface_slot, "fopen") == 0 ||
      strcmp(interface_slot, "fread") == 0) {
    find_interface_pcie_info(interface_name, &numa_node, link_speed, link_width, sizeof(link_speed));
    if (interface_address[0] != '\0' && strcmp(link_speed, "N/A") != 0) {
      snprintf(interface_slot, sizeof(interface_slot), "%s(N%d,%s,x%s)",
               interface_address, numa_node, link_speed, link_width);
    } else if (interface_address[0] != '\0') {
      snprintf(interface_slot, sizeof(interface_slot), "%s(N%d)",
               interface_address, numa_node);
    }
  }
  return strdup(interface_slot);
}

static int
get_val_from_file(char *valsource) {
  FILE *valfile;
  char buffer[6]; /* 0xabcd */
  int ret;

  valfile = fopen(valsource,"r");
  if (valfile == NULL) return -1;

  ret = fread(buffer,1,sizeof(buffer), valfile);
  if (ret != sizeof(buffer)) {
    fclose(valfile);
    return -1;
  }

  ret = (int)strtol(buffer,NULL,0);

  fclose(valfile);
  return ret;

}

void
find_interface_ids(char *interface_name, int *vendor, int *device, int *sub_vend, int *sub_dev) {

  int ret;

  char sysfile[128];  /* gotta love constants */

  /* first the vendor id */
  ret = snprintf(sysfile,128,"/sys/class/net/%s/device/vendor",interface_name);
  *vendor = get_val_from_file(sysfile);

  /* next the device */
  ret = snprintf(sysfile,128,"/sys/class/net/%s/device/device",interface_name);
  *device = get_val_from_file(sysfile);

  /* next the subsystem vendor */
  ret = snprintf(sysfile,128,"/sys/class/net/%s/device/subsystem_vendor",interface_name);
  *sub_vend = get_val_from_file(sysfile);

  /* next the subsystem device */
  ret = snprintf(sysfile,128,"/sys/class/net/%s/device/subsystem_device",interface_name);
  *sub_dev = get_val_from_file(sysfile);

}

#else /* !defined(__linux) */
#include <string.h>

void
find_interface_pcie_info(char *interface_name, int *numa_node, char *link_speed, char *link_width, int len) {
  (void)interface_name;
  if (numa_node) *numa_node = -1;
  if (link_speed && len > 0) { strncpy(link_speed, "N/A", (size_t)len); link_speed[len - 1] = 0; }
  if (link_width && len > 0) { strncpy(link_width, "N/A", (size_t)len); link_width[len - 1] = 0; }
}

char *
find_interface_slot(char *interface_name) {
  (void)interface_name;
  return strdup("N/A");
}

void
find_interface_ids(char *interface_name, int *vendor, int *device, int *sub_vend, int *sub_dev) {
  (void)interface_name;
  if (vendor) *vendor = 0;
  if (device) *device = 0;
  if (sub_vend) *sub_vend = 0;
  if (sub_dev) *sub_dev = 0;
}
#endif /* defined(__linux) */
