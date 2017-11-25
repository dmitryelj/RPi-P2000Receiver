import sys, os, time, socket
import logging
import tzlocal

def getAppPath():
  return os.path.dirname(os.path.realpath(__file__)) + os.sep

def getFileSize(filePath):
    try:
        return os.path.getsize(filePath)
    except:
        return 0

def getFilePath(filePath):
    path, file = os.path.split(filePath)
    return path

def getFileName(filePath):
    path, file = os.path.split(filePath)
    return file

def isFileExist(filePath):
    return os.path.isfile(filePath)

def isRaspberryPi():
    return os.name != "nt" and os.uname()[0] == "Linux"

def isWindows():
    return os.name == "nt"

def getIPAddress():
    try:
        if isWindows():
          hostname = socket.gethostname()
          return socket.gethostbyname(hostname)
        else:
          s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          s.connect(("8.8.8.8", 80))
          return s.getsockname()[0]
    except:
        return "-"

def getCPULoad():
  try:
    return int(psutil.cpu_percent())
  except:
    return 0

def getRAMUsage():
  try:
    return int(psutil.virtual_memory().percent)
  except:
    return 0

def dateAsLocalTZ(dt):
  try:
    tzName = tzlocal.get_localzone()
    return dt.astimezone(tzName)
  except BaseException as e:
    return dt

def dateAsString(dt, format):
  try:
    tzName = tzlocal.get_localzone()
    tmWithTz = dt.astimezone(tzName)        
    return tmWithTz.strftime(format)
  except BaseException as e:
    return str(e)
