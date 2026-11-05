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

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#ifdef NETPERF_STANDALONE_DEBUG
#include <errno.h>
#endif

#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int
read_first_line(const char *path, char *buf, size_t buflen) {
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
  return (len > 0) ? 0 : -1;
}

static void
find_cpu_model(char **cpu_model) {
  char linebuf[256];
  char *cret;

  FILE *proccpu;

  proccpu = fopen("/proc/cpuinfo","r");

  if (NULL == proccpu) {
    *cpu_model = strdup("fopen");
    return;
  }

  do {
    cret = fgets(linebuf,256,proccpu);
    if (NULL != cret) {
      char *target;
      /* OK, so does it start with "model name" ? */
      if (strstr(linebuf,"model name") != NULL) {
	/* one for the money "model name" */
	target = strtok(linebuf,":");
	/* two for the show (the actual model name) */
	target = strtok(NULL,":");
	/* three to get ready - strip the eol */
	target[strlen(target)-1] = 0;
	/* and four to go! */
	*cpu_model = strdup(target+1);
	fclose(proccpu);
	return;
      }
    }
  } while (!feof(proccpu));
  *cpu_model = strdup("model_name");
  fclose(proccpu);
}

static int
find_cpu_freq() {
  char linebuf[256];
  char *cret;

  FILE *proccpu;

  proccpu = fopen("/proc/cpuinfo","r");

  if (NULL != proccpu) {
    do {
      cret = fgets(linebuf,256,proccpu);
      if (NULL != cret) {
        char *target;
        if (strstr(linebuf,"cpu MHz") != NULL) {
	  target = strtok(linebuf,":");
	  target = strtok(NULL,":");
	  if (target != NULL) {
	    fclose(proccpu);
	    return rint(strtod(target+1,NULL));
	  }
	  break;
        }
      }
    } while (!feof(proccpu));
    fclose(proccpu);
  }

  /* Fallback to sysfs cpufreq (kHz -> MHz) on modern kernels/architectures */
  if (read_first_line("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", linebuf, sizeof(linebuf)) == 0 ||
      read_first_line("/sys/devices/system/cpu/cpu0/cpufreq/base_frequency", linebuf, sizeof(linebuf)) == 0 ||
      read_first_line("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", linebuf, sizeof(linebuf)) == 0) {
    long khz = strtol(linebuf, NULL, 10);
    if (khz > 0) {
      return (int)(khz / 1000);
    }
  }

  return -1;
}

static void
find_system_model(char **system_model) {
#if defined(HAVE_LIBSMBIOS)
#if defined(HAVE_SMBIOS_SYSTEMINFO_H)
#include <smbios/SystemInfo.h>
#else
  /* take our best shot - the interface seems simple and stable enough
     that we don't have to require the -dev package be installed */
  extern const char *SMBIOSGetSystemName();
#endif

  char *temp_model;

  /* SMBIOSGetSystemModel allocated */
  temp_model = (char *) SMBIOSGetSystemName();
  if (temp_model)
    *system_model = temp_model;
  else
    *system_model = strdup("SMBIOSGetSystemModel");

#else
  /* Read Linux DMI sysfs directly instead of requiring libsmbios */
  char vendor[128];
  char product[128];
  char combined[260];

  if (read_first_line("/sys/class/dmi/id/product_name", product, sizeof(product)) == 0) {
    if (read_first_line("/sys/class/dmi/id/sys_vendor", vendor, sizeof(vendor)) == 0 &&
        strstr(product, vendor) == NULL) {
      snprintf(combined, sizeof(combined), "%s %s", vendor, product);
      *system_model = strdup(combined);
    } else {
      *system_model = strdup(product);
    }
    return;
  }

  *system_model = strdup("Teach Me SMBIOS");
#endif
  return;
}

void
find_system_info(char **system_model, char **cpu_model, int *cpu_frequency) {

  find_system_model(system_model);
  find_cpu_model(cpu_model);
  *cpu_frequency = find_cpu_freq();

}

#ifdef NETPERF_STANDALONE_DEBUG
int
main(int argc, char *argv[]) {

  char *system_model;
  char *cpu_model;
  int   frequency;

  find_system_info(&system_model,&cpu_model,&frequency);
  printf("system_model %s, cpu_model %s, frequency %d\n",
	 system_model,
	 cpu_model,
	 frequency);

  return 0;

}

#endif
