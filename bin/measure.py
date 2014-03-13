# The Computer Language Benchmarks Game
# $Id: planB.py,v 1.3 2010/03/09 01:49:29 igouy-guest Exp $

"""
measure with psutil
"""

__author__ =  'Isaac Gouy & Ludovic Henry'

import os, sys, time, threading, signal, psutil

from domain import Record

def measure(arg, commandline, delay, maxtime, outFile=None, errFile=None,
            inFile=None, logger=None, affinitymask=None):

   # Monitor :
   # - max memory consumption
   # - user and system time
   # - voluntary and involuntary context switches
   class ProcessMonitor(threading.Thread):

      def __init__(self, process):
         threading.Thread.__init__(self)

         self.process = process
         self.maxmem = 0
         self.time = dict(user=0, system=0)
         self.ctxswitches = dict(voluntary=0, involuntary=0)

         self.setDaemon(1)
         self.start()

      def run(self):
         try:
            while time.time() < start + maxtime:
               if not process.is_running():
                  break

               self.maxmem = max(self.maxmem, self.currentmem())

               self.time['user'] = self.process.get_cpu_times().user
               self.time['system'] = self.process.get_cpu_times().system

               self.ctxswitches['voluntary'] = self.process.get_num_ctx_switches().voluntary
               self.ctxswitches['involuntary'] = self.process.get_num_ctx_switches().involuntary

               time.sleep(delay)
         except psutil.NoSuchProcess:
            pass
         except (OSError, Exception) as e:
            if logger:
               logger.error("%s : %s" % (e.__class__.__name__, e.message))

      def currentmem(self):
         return self.process.get_memory_info().rss \
                  + sum(map(lambda p: p.get_memory_info().rss, self.childrenproc()))

      def childrenproc(self):
         if not self.process.is_running():
            return []
         else:
            return self.process.get_children(recursive=True)

   def set_affinity_mask():
      if sys.platform.startswith("linux") or sys.platform.startswith("win32"):
         if affinitymask:
            proc = psutil.Process(os.getpid())
            cpus = []

            for i in range(psutil.NUM_CPUS):
               if affinitymask & (1 << i) > 0:
                  cpus.append(i)

            proc.set_cpu_affinity(affinitymask)

   def compute_load_per_cpu(cpus0, cpus1):
      cpus = []

      for cpu0, cpu1 in zip(cpus0, cpus1):
         cpus.append(int(round(
            100.0 * (1.0 - float(cpu1.idle - cpu0.idle) / (sum(cpu1._asdict().values()) - sum(cpu0._asdict().values())))
         )))

      return cpus

   try:
      record = Record(arg)

      # psutil cpu is since machine boot, so we need a before measurement
      cpus0 = psutil.cpu_times(percpu=True)
      start = time.time()

      # spawn the program in a separate process
      process = psutil.Popen(commandline,
                             stdout=outFile,
                             stderr=errFile,
                             stdin=inFile,
                             preexec_fn=set_affinity_mask)

      monitor = ProcessMonitor(process)

      # wait for program exit status and resource usage
      timeout = False

      try:
         exitcode = process.wait(timeout=maxtime)
      except psutil.TimeoutExpired:
         timeout = True
         os.kill(process.pid, signal.SIGKILL)

      elapsed = time.time() - start
      cpus1 = psutil.cpu_times(percpu=True)

      # summarize measurements
      if timeout:
         record.setTimedout()
      elif exitcode == os.EX_OK:
         record.setOkay()
      else:
         record.setError()

      record.maxMem = monitor.maxmem / 1024
      record.ctxSwitches = monitor.ctxswitches
      record.cpuLoad = " ".join([str(i) + "%" for i in compute_load_per_cpu(cpus0, cpus1)])

      record.time = dict(user=monitor.time['user'],
                         system=monitor.time['system'],
                         elapsed=elapsed)

   except KeyboardInterrupt:
      os.kill(process.pid, signal.SIGKILL)
   except ZeroDivisionError, (e,err):
      if logger: logger.warn('%s %s',err,'too fast to measure?')
   except (OSError,ValueError) as e:
      if e == ENOENT: # No such file or directory
         if logger:
            logger.warn('%s %s',e,commandline)

         record.setMissing()
      else:
         if logger:
            logger.error(str(e))

         record.setError()
   except Exception, e:
      if logger:
         logger.error("%s : %s" % (e.__class__.__name__, e.message))

   finally:
      return record



