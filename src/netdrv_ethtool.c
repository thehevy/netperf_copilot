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

#if defined(HAVE_CONFIG_H)
#include <config.h>
#endif

#include <unistd.h>
#include <stdlib.h>
#include <sys/types.h>
#include <string.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <errno.h>
#include <net/if.h>
#include <asm/types.h>
#include <linux/sockios.h>

/* alas, direct inclusion of ethtool.h depends on some types not
   normally found in nature, which we must provide or things will be
   quite unhappy. newer ethtool.h include files will it seems be happy
   with our including linux/types.h which will give us __umumble */

#include <linux/types.h>

/* older ethtool.h includes want them without the leading underscores */
typedef unsigned long long u64;
typedef unsigned int       u32;
typedef unsigned short     u16;
typedef unsigned char       u8;

/* ostensibly at this point we should be covered for any ethtool.h? */
#include <linux/ethtool.h>

void
find_driver_info(char *ifname, char *driver, char *version, char *firmware, char *bus, int len) {

  int s;
  int ret;
  struct ifreq ifr;
  struct ethtool_drvinfo drvinfo;

  if (len < 32) return;

  if (!strcmp(ifname,"lo")) {
    /* special case loopback */
    strncpy(driver,"loopback",len);
    strncpy(version,"system",len);
    strncpy(firmware,"N/A",len);
    strncpy(bus,"N/A",len);
    driver[len-1] = 0;
    version[len-1] = 0;
    firmware[len-1] = 0;
    bus[len-1] = 0;
    return;
  }

  s = socket(AF_INET,SOCK_DGRAM,0);

  if (s < 0) {
    strncpy(driver,"SocketFailure",len);
    strncpy(version,"SocketFailure",len);
    strncpy(firmware,"SocketFailure",len);
    strncpy(bus,"SocketFailure",len);
    driver[len-1] = 0;
    version[len-1] = 0;
    firmware[len-1] = 0;
    bus[len-1] = 0;
    return;
  }

  memset(&ifr, 0, sizeof(ifr));
  drvinfo.cmd = ETHTOOL_GDRVINFO;
  strncpy(ifr.ifr_name, ifname, sizeof(ifr.ifr_name)-1);
  ifr.ifr_data = (caddr_t)&drvinfo;

  ret = ioctl(s, SIOCETHTOOL, &ifr);

  if (ret == -1) {
    strncpy(driver,"IoctlFailure",len);
    strncpy(version,"IoctlFailure",len);
    strncpy(firmware,"IoctlFailure",len);
    strncpy(bus,"IoctlFailure",len);
    driver[len-1] = 0;
    version[len-1] = 0;
    firmware[len-1] = 0;
    bus[len-1] = 0;
    close(s);
    return;
  }
  strncpy(driver,drvinfo.driver,len);
  strncpy(version,drvinfo.version,len);
  strncpy(firmware,drvinfo.fw_version,len);
  strncpy(bus,drvinfo.bus_info,len);
  driver[len-1] = 0;
  version[len-1] = 0;
  firmware[len-1] = 0;
  bus[len-1] = 0;

  close(s);

  return;
}

/* Query 100G/200G/400G/800G link speed (Mbps), RX/TX ring sizes, and combined channels */
void
find_driver_ext_info(char *ifname, int *link_speed_mbps, int *rx_ring, int *tx_ring, int *combined_channels) {
  int s;
  struct ifreq ifr;
  char sysfile[160];
  FILE *f;

  if (link_speed_mbps) *link_speed_mbps = -1;
  if (rx_ring) *rx_ring = -1;
  if (tx_ring) *tx_ring = -1;
  if (combined_channels) *combined_channels = -1;

  if (ifname == NULL || ifname[0] == '\0' || strcmp(ifname, "lo") == 0) {
    return;
  }

  /* Read link speed from /sys/class/net/<if>/speed (supports 100000, 200000, 400000, 800000 Mbps) */
  if (link_speed_mbps) {
    snprintf(sysfile, sizeof(sysfile), "/sys/class/net/%s/speed", ifname);
    f = fopen(sysfile, "r");
    if (f != NULL) {
      char buf[32];
      if (fgets(buf, sizeof(buf), f) != NULL) {
        *link_speed_mbps = atoi(buf);
      }
      fclose(f);
    }
  }

  s = socket(AF_INET, SOCK_DGRAM, 0);
  if (s < 0) {
    return;
  }

#ifdef ETHTOOL_GLINKSETTINGS
  if (link_speed_mbps && *link_speed_mbps <= 0) {
    struct {
      struct ethtool_link_settings req;
      __u32 link_mode_data[3 * 127];
    } ecmd;
    memset(&ecmd, 0, sizeof(ecmd));
    memset(&ifr, 0, sizeof(ifr));
    ecmd.req.cmd = ETHTOOL_GLINKSETTINGS;
    strncpy(ifr.ifr_name, ifname, sizeof(ifr.ifr_name) - 1);
    ifr.ifr_data = (caddr_t)&ecmd;
    if (ioctl(s, SIOCETHTOOL, &ifr) == 0 && ecmd.req.link_mode_masks_nwords < 0) {
      ecmd.req.link_mode_masks_nwords = -ecmd.req.link_mode_masks_nwords;
      if (ioctl(s, SIOCETHTOOL, &ifr) == 0 && ecmd.req.speed != 0 && ecmd.req.speed != (__u32)-1) {
        *link_speed_mbps = (int)ecmd.req.speed;
      }
    }
  }
#endif

#ifdef ETHTOOL_GRINGPARAM
  if (rx_ring || tx_ring) {
    struct ethtool_ringparam ep;
    memset(&ep, 0, sizeof(ep));
    memset(&ifr, 0, sizeof(ifr));
    ep.cmd = ETHTOOL_GRINGPARAM;
    strncpy(ifr.ifr_name, ifname, sizeof(ifr.ifr_name) - 1);
    ifr.ifr_data = (caddr_t)&ep;
    if (ioctl(s, SIOCETHTOOL, &ifr) == 0) {
      if (rx_ring) *rx_ring = (int)ep.rx_pending;
      if (tx_ring) *tx_ring = (int)ep.tx_pending;
    }
  }
#endif

#ifdef ETHTOOL_GCHANNELS
  if (combined_channels) {
    struct ethtool_channels ech;
    memset(&ech, 0, sizeof(ech));
    memset(&ifr, 0, sizeof(ifr));
    ech.cmd = ETHTOOL_GCHANNELS;
    strncpy(ifr.ifr_name, ifname, sizeof(ifr.ifr_name) - 1);
    ifr.ifr_data = (caddr_t)&ech;
    if (ioctl(s, SIOCETHTOOL, &ifr) == 0) {
      *combined_channels = (int)ech.combined_count;
    }
  }
#endif

  close(s);
}

#if defined(NETPERF_STANDALONE_DEBUG)
int
main(int argc, char *argv[]) {

  char driver[32];
  char version[32];
  char firmware[32];
  char businfo[32];

  if (argc != 2) {
    fprintf(stderr,"%s <interface>\n",argv[0]);
    return -1;
  }

  find_driver_info(argv[1],driver, version, firmware, businfo, 32);

  printf("For %s driver %s version %s firmware %s businfo %s\n",
	 argv[1],driver, version, firmware, businfo);

  return 0;
}
#endif
