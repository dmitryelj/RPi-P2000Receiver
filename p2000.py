# P2000 RTL-SDR based Raspberry Pi autonomous receiver
# dmitryelj@gmail.com
#
# To run: python3 p2000.py [lcd=true|false]
# To see messages in browser: http://IP_ADDRESS:8000
#
# Install libraries first:
# sudo apt-get install python3 python3-pip
# sudo pip3 install numpy pillow tzlocal spidev RPi.GPIO
# multimon-ng and rtl-sdr libraries also required (see README.md)

import time
import sys
import subprocess
import os
import threading
import re
import textwrap
import json
import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import libTFT
import utils

# Main parameters
frequency = "169.65M"
gain = 20           # gain, een getal tussen 0-50
correction = 0      # specifieke ppm-afwijking van RTL-SDR
messagesLimit = 5000
no_lcd = False
debug = False

# Internal server
PORT_NUMBER = 8000
httpd = None

# Messages priority
PRIORITY0 = 0
PRIORITY1 = 1
PRIORITY2 = 2
PRIORITY3 = 3

# Main view and data
mainView = None
messages = []
capcodesDict = dict()
is_active = False

class MessageItem(object):
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.groupid = ""
        self.receivers = ""
        self.body = ""
        self.priority = 0
    
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

# UI Main view
class UIMainView(object):
  def __init__(self):
      self.tft = libTFT.lcdInit()
      self.tft.clear_display(self.tft.WHITE)
      self.tft.led_on(True)
      self.tft.onButton1 = lambda: self.onButton1()
      self.tft.onButton2 = lambda: self.onButton2()
      self.tft.onButton3 = lambda: self.onButton3()
      self.lines_cnt = 11
      self.lines_width = 37
      self.dataPos = 0
      self.pause = False
      self.dataLock = threading.Lock()
      self.initUI()
      self.updateUI()
      self.draw()
      
  def onButton1(self):
      if self.dataPos > 0:
          self.dataPos -= 1
      self.pause = False
      self.updateUI()

  def onButton2(self):
      self.dataPos += 1
      self.pause = False
      self.updateUI()

  def onButton3(self):
      self.pause = not self.pause
      if self.pause is False:
          self.dataPos = 0
      self.updateUI()

  def initUI(self):
      # Header
      self.headerLeft = libTFT.UILabel("", 4,5, textColor=self.tft.BLACK, backColor=self.tft.WHITE, fontS = 7)
      self.tft.controls.append(self.headerLeft)
      self.headerRight = libTFT.UILabel("IP: -", 130,5, textColor=self.tft.BLACK, backColor=self.tft.WHITE, fontS = 7)
      self.tft.controls.append(self.headerRight)
      self.tft.controls.append(libTFT.UILine(0, 26, 320, 26, self.tft.BLACK))
      # Data
      lines_cnt = 20
      self.dataLabels = []
      for p in range(self.lines_cnt):
          label = libTFT.UILabel("", 4, 30 + 18*p, textColor=self.tft.BLACK, backColor=self.tft.WHITE, fontS = 7)
          self.tft.controls.append(label)
          self.dataLabels.append(label)

  def updateUI(self):
      global messages
      self.headerLeft.text = "PAUSED           " if self.pause else "{} messages".format(len(messages))
      self.headerRight.text = "IP: {}:{}".format(utils.getIPAddress(), PORT_NUMBER)

      # If paused, no data update
      if self.pause:
          self.draw()
          return
      
      self.dataLock.acquire()
      line_index = 0
      for p in range(self.lines_cnt):
          try:
              message = messages[self.dataPos + p] if self.dataPos + p < len(messages) else None
              if message is None:
                  # No message: add empty line
                  if line_index < self.lines_cnt:
                      self.dataLabels[line_index].text = " "*self.lines_width
                      line_index += 1
              else:
                  # Group and datetime
                  if line_index < self.lines_cnt:
                      header_str = "{}. {}".format(message.groupid, message.timestamp)
                      self.dataLabels[line_index].text = self.strExpandToSize(header_str, self.lines_width)
                      self.dataLabels[line_index].textColor = self.tft.BLACK
                      line_index += 1
                  
                  # Receivers
                  receivers = "To: {}".format(message.groupid, message.receivers)
                  receivers_lines = self.strToStringsListWithSize(receivers, self.lines_width)
                  for s in receivers_lines:
                      if line_index >= self.lines_cnt: break
                      
                      self.dataLabels[line_index].text = self.strExpandToSize(s, self.lines_width)
                      self.dataLabels[line_index].textColor = self.tft.BLACK
                      line_index += 1
                  
                  # Body
                  msg_body_lines = self.strToStringsListWithSize(message.body, self.lines_width)
                  msg_color = self.tft.BLACK
                  if message.priority == PRIORITY1:
                      msg_color = self.tft.GREEN
                  elif message.priority == PRIORITY2:
                      msg_color = self.tft.BLUE
                  elif message.priority == PRIORITY3:
                      msg_color = self.tft.RED
                  for s in msg_body_lines:
                      if line_index >= self.lines_cnt: break

                      self.dataLabels[line_index].text = self.strExpandToSize(s, self.lines_width)
                      self.dataLabels[line_index].textColor = msg_color
                      line_index += 1
      
                  # Divider
                  if line_index < self.lines_cnt:
                      self.dataLabels[line_index].text = self.strExpandToSize("", self.lines_width)
                      self.dataLabels[line_index].textColor = self.tft.BLACK
                      line_index += 1
                        
          except BaseException as e:
              exc_type, exc_obj, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              print("updateUI::Error in line: ", exc_type, fname, exc_tb.tb_lineno, str(e))

      self.dataLock.release()
      self.draw()

  def strToStringsListWithSize(self, txt, size):
      return textwrap.wrap(txt, width=size)
  
  def strExpandToSize(self, txt, size):
      return ('{:' + str(size) + '}').format(txt)

  def draw(self):
      self.dataLock.acquire()
      try:
          self.tft.draw()
      except:
          pass
      self.dataLock.release()
  
  def mainloop(self):
      self.tft.mainloop()


# Empty fake view, if UI is disabled
class UIEmptyView(object):
    def __init__(self):
        pass
    
    def updateUI(self):
        pass

    def mainloop(self):
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break


# HTTP server.
class HTTPHandler(BaseHTTPRequestHandler):
  
    def do_ReadFile(self, fileName):
        abs_path = os.path.abspath(__file__)
        dir_path = os.path.dirname(abs_path)
        content = b""
        try:
            # All stuff stored in 'http' subfolder
            file_path = dir_path + "/http" + fileName
            print("Read %s" % file_path)
            with open(file_path, 'rb') as datafile:
                content = datafile.read()
            print("Done, %sb" % len(content))
        except Exception as e:
            print("do_ReadFile Error: %s" % str(e))
        return content
          
    def make_Reboot(self):
        print("Reboot after 5s")
        try:
            if utils.isRaspberryPi():
                subprocess.Popen("(sleep 5 ; exec sudo reboot) &", stdout=subprocess.PIPE, shell=True)
        except:
            pass

    def make_Poweroff(self):
      print("Power off after 5s")
      try:
          if utils.isRaspberryPi():
              subprocess.Popen("(sleep 5 ; exec sudo halt) &", stdout=subprocess.PIPE, shell=True)
      except:
          pass

    def do_getMessagesAsJson(self):
        global messages
        js_list = map((lambda x: x.toJSON()), messages)
        j = '[' + ", ".join(js_list) + ']'
        return j.encode("utf-8")
  
    def file_isSupported(self, fileName):
        types = [ '.css', '.htm', '.html', '.js', '.gif', '.jpeg', '.jpg', '.png', '.svg', '.text', '.txt', '.woff', '.ttf', '.eot', '.ico' ]
        types_applied = [x for x in types if x in fileName.lower()]
        return len(types_applied) > 0
    
    def ext_toResponceType(self, fileName):
        content_types = {
            '.css': 'text/css',
            '.gif': 'image/gif',
            '.ico': 'image/x-icon',
            '.htm': 'text/html',
            '.html': 'text/html',
            '.jpeg': 'image/jpeg',
            '.jpg': 'image/jpg',
            '.svg': 'image/svg',
            '.js': 'text/javascript',
            '.png': 'image/png',
            '.text': 'text/plain',
            '.txt': 'text/plain',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject',
            '.woff': 'application/font-woff'
        }
        for key, value in content_types.items():
            if key in fileName.lower():
                return value
        
        return "error: unknown type"
            
    def do_HEAD(self):
        print("HEAD:", self.path)
        self.send_response(200)
        if self.path == "/":
            self.send_header("Content-type", "text/html")
        else:
            self.send_header("Content-type", "application/json")
        self.end_headers()

    def do_GET(self):
        responce = b"error"
        responceCode = 400
        responceType = "application/json"
        try:
            print("GET:", self.path)
            # Main page: show html
            if self.path == "/":
                responceCode = 200
                responceType = "text/html"
                responce = self.do_ReadFile("/index.html")
            # RPi commands: reboot
            elif self.path == "/api/reboot":
                self.make_Reboot()
                responceCode = 200
                responceType = "text/html"
                responce = b"Reboot after 5s"
            # RPi commands: power off
            elif self.path == "/api/poweroff":
                self.make_Poweroff()
                responceCode = 200
                responceType = "text/html"
                responce = b"Power off after 5s"
            # API: get received messages
            elif self.path == "/api/messages":
                responceCode = 200
                responceType = "application/json"
                responce = self.do_getMessagesAsJson()
            # Check if file is supported
            elif self.file_isSupported(self.path):
                responceCode = 200
                responceType = self.ext_toResponceType(self.path)
                responce = self.do_ReadFile(self.path)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print("Error: ", exc_tb.tb_lineno, str(e))
        
        self.send_response(responceCode)
        self.send_header("Content-type", responceType)
        self.end_headers()
        self.wfile.write(responce)

def checkRTLSDR():
    res = True
    # Helper: check that RTL-SDR software is installed
    process = subprocess.Popen("rtl_fm", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait for the process to finish
    out, err = process.communicate()
    error_str = err.decode('utf8')
    if "not found" in error_str:
        print("rtl_fm: not found")
        res = False
    else:
        print("rtl_fm: ok")

    process = subprocess.Popen("multimon-ng -h", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait for the process to finish
    out, err = process.communicate()
    error_str = err.decode('utf8')
    if "not found" in error_str:
        print("multimon-ng: not found")
        res = False
    else:
        print("multimon-ng: ok")

    return res

def loadCapcodesDict():
    global capcodesDict
    # Load capcodes dictionary: "capcode,description" pairs
    try:
        abs_path = os.path.abspath(__file__)
        dir_path = os.path.dirname(abs_path)
        print("Loading {}".format(dir_path + "/capcodes.txt"))
        with open(dir_path + "/capcodes.txt", "r") as text_file:
            lines = text_file.readlines()
            for s in lines:
                fields = s.split(',')
                if len(fields) == 2:
                    capcodesDict[fields[0]] = fields[1].strip()
    except:
        pass

if __name__ == "__main__":
    print("Raspberry Pi P2000 decoder v0.2b")
    print("Run:\npython3 p2000.py lcd=true|false")
    print("")

    parser = argparse.ArgumentParser()
    parser.add_argument("--lcd", dest="lcd", default="true")
    args = parser.parse_args()
    if args.lcd == 'False' or args.lcd == 'false' or args.lcd == '0':
        no_lcd = True

    print("LCD in use:", "no" if no_lcd else "yes")
    rtl_found = checkRTLSDR()
    print("")

    loadCapcodesDict()
    print(len(capcodesDict.keys()), "records loaded")
    print("")

    # Debug=True - without receiver, for simulation: gcc debugtest.c -odebugtest)
    if utils.isRaspberryPi() is False:
        debug = True

    if rtl_found is False and debug is False:
        print("App done, configuration is not complete")
        sys.exit(0)

    # Data receiving thread
    def dataThreadFunc():
        global is_active, mainView, frequency, messages, capcodesDict, debug
      
        cmd = "rtl_fm -f {} -M fm -s 22050 -g {} -p {} | multimon-ng -a FLEX -t raw -".format(frequency, gain, correction)
        print("Run process", cmd)
        if debug:
            abs_path = os.path.abspath(__file__)
            dir_path = os.path.dirname(abs_path)
            cmd = dir_path + "/./debugtest"
            print("Debug process", cmd)
        
        multimon_ng = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        try:
            while True:
                if is_active is False: break
                
                # Parsing based on
                # https://nl.oneguyoneblog.com/2016/08/09/p2000-ontvangen-decoderen-raspberry-pi/
                line = multimon_ng.stdout.readline().decode('utf8')
                multimon_ng.poll()
                if line.startswith('FLEX'):
                    print(line.strip())
                    if line.__contains__("ALN"):
                        flex = line[0:5]
                        timestamp = line[6:25]
                        message = line[58:].strip()
                        groupid = line[35:41].strip()
                        capcode = line[43:52].strip()

                        regex_prio1 = "^A\s?1|\s?A\s?1|PRIO\s?1|^P\s?1"
                        regex_prio2 = "^A\s?2|\s?A\s?2|PRIO\s?2|^P\s?2"
                        regex_prio3 = "^B\s?1|^B\s?2|^B\s?3|PRIO\s?3|^P\s?3|PRIO\s?4|^P\s?4"
         
                        pr = PRIORITY0
                        if re.search(regex_prio1, message, re.IGNORECASE):
                            pr = PRIORITY3
                        elif re.search(regex_prio2, message, re.IGNORECASE):
                            pr = PRIORITY2
                        elif re.search(regex_prio3, message, re.IGNORECASE):
                            pr = PRIORITY1

                        # print("MSG", groupid, capcode, message)
                        
                        # Get name from capcode, if exist
                        receiver_name = "{} ({})".format(capcodesDict[capcode], capcode) if capcode in capcodesDict else capcode
                        
                        # If the message was already received, only add receivers capcode
                        if len(messages) > 0 and messages[0].body == message:
                            messages[0].receivers += (", " + receiver_name)
                        else:
                            msg = MessageItem()
                            msg.groupid = groupid
                            msg.receivers = receiver_name
                            msg.body = message
                            msg.priority = pr
                            messages.insert(0, msg)
            
                        # Limit the list size
                        if len(messages) > messagesLimit:
                            messages = messages[:messagesLimit]
                        
                        # Update UI
                        mainView.updateUI()

        except KeyboardInterrupt:
            os.kill(multimon_ng.pid, 9)
        except BaseException as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print("dataThreadFunc::Error in line: ", exc_type, fname, exc_tb.tb_lineno, str(e))
            os.kill(multimon_ng.pid, 9)
        print("Data thread stopped")

    # HTTP server handling thread
    def httpServerFunc():
        global httpd
        print("Http server started")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()
        print("Http server stopped")

    is_active = True

    mainView = UIMainView() if no_lcd is False else UIEmptyView()

    dataThread = threading.Thread(target=dataThreadFunc)
    dataThread.start()

    httpd = HTTPServer(('', PORT_NUMBER), HTTPHandler)
    serverThread = threading.Thread(target=httpServerFunc)
    serverThread.start()

    # Run UI
    mainView.mainloop()

    is_active = False
    httpd.shutdown()

    print("App done")




