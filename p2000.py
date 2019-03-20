# P2000 RTL-SDR based Raspberry Pi autonomous receiver
# dmitryelj@gmail.com
#
# To run: python3 p2000.py [lcd=true|false]
# To see messages in browser: http://IP_ADDRESS:8000
#
# Install libraries first:
# sudo apt-get install python3 python3-pip
# sudo pip3 install numpy pillow tzlocal spidev RPi.GPIO requests
# multimon-ng and rtl-sdr libraries also required (see README.md)

import time
import sys
import subprocess
import os
import threading
import re
import fnmatch
import textwrap
import json
import argparse
import requests
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from websocket_server import WebsocketServer
import libTFT
import utils

# Main parameters
frequency = "169.65M"  # FLEX
# frequency = "172.45M"  # POCSAG
gain = 20           # gain, een getal tussen 0-50
correction = 0      # specifieke ppm-afwijking van RTL-SDR
messagesLimit = 5000
no_lcd = False
debug = False

# Internal server
PORT_NUMBER = 8000
httpd = None
# Websocket server
PORT_NUMBER_WS = 8001
websocket = None

# Posting to 3rd party server (not implemented, see MessageItem class)
post_delay_s = 15.0

# Messages priority
PRIORITY0 = 0
PRIORITY1 = 1
PRIORITY2 = 2
PRIORITY3 = 3
PRIORITY4 = 4

# Sender type
SENDER_UNKNOWN = 0
SENDER_BRAND = 1
SENDER_POLICE = 2
SENDER_AMBU = 3
SENDER_TEST = 16
SENDER_POCSAG = 64
SENDER_POCSAG_ALPHA = 65
SENDER_POCSAG_NUMERIC = 66
SENDER_POCSAG_EMPTY = 67

# Main view and data
mainView = None
messages = []
capcodesDict = dict()
filtersList = []
is_active = False

# Capcodes classification
capcodes_police = set()
capcodes_fire = set()
capcodes_ambu = set()


class MessageItem(object):
    __slots__ = ['timestamp', 'timereceived', 'groupid', 'receivers', 'capcodes', 'body', 'priority', 'sender', 'is_posted']
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timereceived = time.time()
        self.groupid = ""
        self.receivers = ""
        self.capcodes = []
        self.body = ""
        self.priority = 0
        self.sender = 0;
        self.is_posted = False
    
    def toJSON(self):
        data = {"timestamp": self.timestamp,
                "timereceived": self.timereceived,
                "groupid": self.groupid,
                "receivers": self.receivers,
                "capcodes": self.capcodes,
                "body": self.body,
                "priority": self.priority,
                "sender": self.sender,
                "is_posted": self.is_posted}
        return json.dumps(data, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def postToServer(self):
        try:
            print("POST:", self.toJSON())
            # r = requests.post("http://mysuperserver.com", data=dict(payload=self.toJSON()))
            # print("POST result:", r.status_code, r.reason)
            # print("POST text:", r.text)
            self.is_posted = True
        except:
            pass

    def isPosted(self):
        return self.is_posted

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
                  elif message.priority == PRIORITY3 or message.priority == PRIORITY4:
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
class UIConsoleView(object):
    def __init__(self):
        pass
    
    def updateUI(self):
        pass

        # global messages
        # print("\x1b[2J")  # Clear console
        # max_cnt = 10
        # print("\x1b[0;0H" + '\x1b[1m' + "Last {} messages\n".format(max_cnt) + '\x1b[0m') # Cursor to 0,0
        # for idx, msg in enumerate(messages):
        #     # Header and time
        #     print('\x1b[1;37m' + "{}".format(msg.timestamp) + '\x1b[0m') # Grey
        #     # Group and receivers
        #     print("To: {}".format(msg.groupid, msg.receivers))
        #     # Body
        #     msg_color = '\x1b[1;30m' # Black
        #     if msg.priority == PRIORITY1:
        #         msg_color = '\x1b[1;32m' # Green
        #     elif msg.priority == PRIORITY2:
        #         msg_color = '\x1b[1;34m' # Blue
        #     elif msg.priority == PRIORITY3 or msg.priority == PRIORITY4:
        #         msg_color = '\x1b[1;31m' # Red
        #     print(msg_color + msg.body + '\x1b[0m')
        #     print("")
        #
        #     if idx >= max_cnt: break

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
            # print("Read %s" % file_path)
            with open(file_path, 'rb') as datafile:
                content = datafile.read()
            # print("Done, %sb" % len(content))
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
    if "not found" in error_str or "not recognized" in error_str:
        print("rtl_fm: not found, please install RTL-SDR software")
        res = False
    else:
        print("rtl_fm: ok")

    # Linux only: check that multimon-ng is installed
    if os.name != 'nt':
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

def loadCapcodesDict(filename):
    # Load capcodes dictionary: "capcode,description" pairs
    capcodes = dict()
    try:
        print("Loading {}".format(filename))
        with open(filename, "r") as text_file:
            lines = text_file.readlines()
            for s in lines:
                if s[0] == '#':
                    continue

                fields = s.split(',')
                if len(fields) == 2:
                    capcodes[fields[0].strip()] = fields[1].strip()
    except:
        pass
    return capcodes

def loadCapcodesSet(filename):
    # Load capcodes list from a raw text file: 00001, 00002, ...
    capcodes = set()
    try:
        print("Loading capcodes for classifier {}".format(filename))
        with open(filename, "r") as text_file:
            lines = text_file.readlines()
            for s in lines:
                if s[0] == '#':
                    continue
                
                fields = s.strip().split(', ')
                capcodes.update(fields)
    except:
          pass
    print("  {} loaded".format(len(capcodes)))
    return capcodes

def loadFilter(filterFile):
    global filtersList
    filtersList = []
    try:
        with open(filterFile, "r") as text_file:
            lines = text_file.readlines()
            lines_strip = map((lambda s: s.strip()), lines)
            filtersList = list(filter(lambda s: len(s) > 0 and s[0:1] != "#" and s[0:1] != ";", lines_strip))
    except:
        pass

def checkFilter(capcode):
    global filtersList
    # If filter not loaded, disable
    if len(filtersList) == 0:
        return True

    # Check if capcode applied to at least one filter
    for f_str in filtersList:
        if fnmatch.fnmatch(capcode, f_str):
            return True
    return False

def getSender(capcode, message):
    global capcodes_police, capcodes_fire, capcodes_ambu
    # Check from capcodes list
    if capcode in capcodes_police:
        return SENDER_POLICE
    if capcode in capcodes_fire:
        return SENDER_BRAND
    if capcode in capcodes_ambu:
        return SENDER_AMBU

    # Try to analyse the text


    return SENDER_UNKNOWN

if __name__ == "__main__":
    print("")
    print("P2000 decoder v0.33 by Dmitrii Eliseev\n")
    print("Run:\npython3 p2000.py --lcd=true|false [--filter=filter.txt] [--capcodes=capcodes.txt]")
    print("")
    print("Server running: http://{}:{}".format(utils.getIPAddress(), PORT_NUMBER))
    print("API (GET): http://{}:{}/api/messages".format(utils.getIPAddress(), PORT_NUMBER))
    print("Websocket: ws://{}:{}".format(utils.getIPAddress(), PORT_NUMBER_WS))
    print("")

    parser = argparse.ArgumentParser()
    parser.add_argument("--lcd", dest="lcd", default="false")
    parser.add_argument("--filter", dest="filter", default="")
    parser.add_argument("--capcodes", dest="capcodes", default="")
    args = parser.parse_args()

    # Set current folder
    abs_path = os.path.abspath(__file__)
    dir_path = os.path.dirname(abs_path)
    os.chdir(dir_path)

    # Check LCD connection
    if args.lcd == 'False' or args.lcd == 'false' or args.lcd == '0':
        no_lcd = True
    print("LCD in use:", "no" if no_lcd else "yes")
    print("Frequency:", frequency)
    # Check RTLSDR connection
    rtl_found = checkRTLSDR()
    print("")

    # Load capcodes file
    capcodes_path = args.capcodes

    if capcodes_path == "":
        capcodes_path = dir_path + os.sep + "capcodes.txt"
    capcodesDict = loadCapcodesDict(capcodes_path)
    print("Capcodes: {} records loaded".format(len(capcodesDict.keys())))

    # Load filter file
    filter_path = args.filter
    if len(filter_path) > 0:
        loadFilter(filter_path)
    print("Filter: {} strings loaded".format(len(filtersList)))
    print("")

    # Load capcodes classifier
    capcodes_police = loadCapcodesSet(dir_path + os.sep + "cc_police.txt")
    capcodes_fire = loadCapcodesSet(dir_path + os.sep + "cc_fire.txt")
    capcodes_ambu = loadCapcodesSet(dir_path + os.sep + "cc_ambu.txt")

    # Debug=True - without receiver, for simulation: gcc debugtest.c -odebugtest)
    # if utils.isRaspberryPi() is False:
    debug = False

    if rtl_found is False and debug is False:
        print("App finished, configuration is not complete")
        sys.exit(0)

    # Data receiving thread
    def dataThreadFunc():
        global is_active, mainView, frequency, messages, capcodesDict, debug

        cmd = "rtl_fm -f {} -M fm -s 22050 -g {} -p {} | multimon-ng -a FLEX -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -t raw -".format(frequency, gain, correction)
        abs_path = os.path.abspath(__file__)
        dir_path = os.path.dirname(abs_path)
        if os.name == 'nt':
            cmd = cmd.replace("multimon-ng", "win32\\multimon-ng.exe")
        # print("Run process:", cmd)
        if debug:
            cmd = dir_path + "/./debugtest"
            # print("Debug process", cmd)
        
        multimon_ng = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        try:
            while True:
                if is_active is False: break
                
                # Read line from process
                line = multimon_ng.stdout.readline()
                try:
                    line = line.decode('utf8', 'backslashreplace')
                except:
                    line = ""
                    print("Warning: cannot decode utf8 string")
                multimon_ng.poll()
                if line.startswith('FLEX'):
                    if line.__contains__("ALN"):
                        # Parsing based on
                        # https://nl.oneguyoneblog.com/2016/08/09/p2000-ontvangen-decoderen-raspberry-pi/
                        # Message sample:
                        # FLEX: 2018-07-29 11:43:27 1600/2/K/A 10.120 [001523172] ALN A1 Boerhaavelaan HAARLM : 16172
                        line_data = line.split(' ')
                        flex = line[0:5]
                        timestamp = line_data[1] + " " + line_data[2]
                        message = line[line.find("ALN")+4:].strip()
                        groupid = line_data[4].strip()
                        capcode = line_data[5].replace('[', '').replace(']', '') # line[43:52].strip()
                        
                        # Apply filter
                        if checkFilter(capcode) is False:
                            continue
                        
                        print(line.strip())

                        regex_prio1 = "^A\s?1|\s?A\s?1|PRIO\s?1|^P\s?1"
                        regex_prio2 = "^A\s?2|\s?A\s?2|PRIO\s?2|^P\s?2"
                        regex_prio3 = "^B\s?1|^B\s?2|^B\s?3|PRIO\s?3|^P\s?3"
                        regex_prio4 = "^PRIO\s?4|^P\s?4"
                        msg_words = message.split(' ')
                        msg_start = ""
                        if len(msg_words) > 0:
                            msg_start += msg_words[0]
                        if len(msg_words) > 1:
                            msg_start += ' ' + msg_words[1]
                        pr = PRIORITY0
                        if re.search(regex_prio1, msg_start, re.IGNORECASE):
                            pr = PRIORITY1
                        elif re.search(regex_prio2, msg_start, re.IGNORECASE):
                            pr = PRIORITY2
                        elif re.search(regex_prio3, msg_start, re.IGNORECASE):
                            pr = PRIORITY3
                        elif re.search(regex_prio4, msg_start, re.IGNORECASE):
                            pr = PRIORITY4

                        # print("MSG", groupid, capcode, message)
                        # print("DATA", line_data)

                        # Get name from capcode, if exist
                        receiver_name = "{} ({})".format(capcodesDict[capcode], capcode) if capcode in capcodesDict else capcode
                        
                        # If the message was already received, only add receivers capcode
                        if len(messages) > 0 and messages[0].body == message:
                            messages[0].receivers += (", " + receiver_name)
                            messages[0].capcodes.append(capcode)
                            if messages[0].sender == SENDER_UNKNOWN:
                                messages[0].sender = getSender(capcode, message)
                        else:
                            msg = MessageItem()
                            msg.groupid = groupid
                            msg.receivers = receiver_name
                            msg.capcodes = [capcode]
                            msg.body = message
                            msg.sender = getSender(capcode, message)
                            msg.priority = pr
                            msg.timestamp = timestamp
                            msg.is_posted = False
                            messages.insert(0, msg)
            
                        # Limit the list size
                        if len(messages) > messagesLimit:
                            messages = messages[:messagesLimit]
                        
                        # Update UI
                        mainView.updateUI()
                if line.startswith('POCSAG'):
                    # Message sample:
                    # POCSAG1200: Address:  104206  Function: 3  Alpha:   CompaxoHybridO|[Onderwerp:]Min. afw. ruimtetemp.-H: Vriescel 2042|[Inhoud:]<EOT><EOT>
                    # POCSAG1200: Address:    1000  Function: 3
                    # POCSAG1200: Address:  175557  Function: 0  Numeric: 0715828347

                    print(line.strip())
                    
                    receiver, message, type, pr = None, "-", SENDER_POCSAG, PRIORITY2
                    
                    addr_index = line.find("Address:")
                    func_index = line.find("Function:")
                    alpha_index = line.find("Alpha:")
                    numeric_index = line.find("Numeric:")
                    if addr_index != -1 and func_index != -1:
                        receiver = line[addr_index + 9:func_index].strip()
                    if alpha_index != -1:
                        type = SENDER_POCSAG_ALPHA
                        message = line[alpha_index+6:].strip()
                    if numeric_index != -1:
                        type = SENDER_POCSAG_NUMERIC
                        message = line[numeric_index+9:].strip()
                    if message == "-":
                        type = SENDER_POCSAG_EMPTY

                    if receiver is None:
                        continue

                    # If the message was already received, only add receivers number
                    if len(messages) > 0 and messages[0].body == message:
                        messages[0].receivers += (", " + receiver)
                        messages[0].capcodes.append(receiver)
                    else:
                        msg = MessageItem()
                        msg.groupid = 0
                        msg.receivers = receiver
                        msg.capcodes = [receiver]
                        msg.body = message
                        msg.sender = type
                        msg.priority = pr
                        msg.is_posted = False
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

    # Websocket server
    def websocketThreadFunc():
        global websocket

        def on_connected(client, server):
            print("Websocket: client-%d connected" % client['id'])

        def on_disconnected(client, server):
            print("Websocket: client-%d disconnected" % client['id'])

        def on_message_received(client, server, message):
            print("Websocket: client-%d sent message: %s" % (client['id'], message))

        print("Websocket thread started")
        websocket.set_fn_new_client(on_connected)
        websocket.set_fn_client_left(on_disconnected)
        websocket.set_fn_message_received(on_message_received)
        websocket.run_forever()

    # Posting data to 3rd party server (optional) and to the websocket server
    def postThreadFunc():
        global websocket

        print("Data post thread started")
        while True:
            if is_active is False:
                break

            try:
                now = time.time()
                for msg in messages:
                    if msg.isPosted() is False and now - msg.timereceived >= post_delay_s:
                        msg.postToServer()
                        websocket.send_message_to_all(msg.toJSON())
            except BaseException as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                print("postThreadFunc error in line: ", exc_type, exc_tb.tb_lineno, str(e))

            time.sleep(1.0)
        print("Data post thread stopped")

    is_active = True

    mainView = UIMainView() if no_lcd is False else UIConsoleView()

    dataThread = threading.Thread(target=dataThreadFunc)
    dataThread.start()

    websocket = WebsocketServer(PORT_NUMBER_WS, host="0.0.0.0")
    weThread = threading.Thread(target=websocketThreadFunc)
    weThread.start()

    httpd = HTTPServer(('', PORT_NUMBER), HTTPHandler)
    serverThread = threading.Thread(target=httpServerFunc)
    serverThread.start()

    postThread = threading.Thread(target=postThreadFunc)
    postThread.start()

    # Run UI
    mainView.mainloop()

    is_active = False
    httpd.shutdown()
    websocket.shutdown()

    print("App done")




