P2000 rtl-sdr based messages receiver.

# Features

- Standalone P2000 messages receiving (RTL-SDR compatible receiver required)

- Cross-platform (can work on Windows, Linux and Mac)

- Show messages on LCD or via web browser interface from any home device

- Capcodes phonebook (note: user should fill capcodes.txt before using)

- Capcodes optional filter (white list)

- 5000 messages memory (can be increased in settings)

- Data post to 3rd party server (optional)

- Websockets support

# Screenshots

![View](/screenshots/RPi_P2000.jpg)

![View](/screenshots/RPi_P2000_web.jpg)

![View](/screenshots/ConsoleOutput.jpg)

# Install (RPi)

0) Before begin:

sudo apt-get install build-essential cmake unzip pkg-config

sudo apt-get install libusb-1.0-0-dev

sudo pip3 install wheel
sudo pip3 install setuptools
sudo pip3 install tzlocal

1) Install RTL-SDR:

git clone git://git.osmocom.org/rtl-sdr.git

cd rtl-sdr

mkdir build

cd build

cmake ../ -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON

make

sudo make install

sudo ldconfig


"rtl_test" command should work after this install.

2) Install multimon-ng:

sudo apt-get -y install git cmake build-essential libusb-1.0 qt4-qmake libpulse-dev libx11-dev qt4-default

git clone https://github.com/Zanoroy/multimon-ng.git

cd multimon-ng

mkdir build

cd build

qmake ../multimon-ng.pro

make

sudo make install


"multimon-ng" command should work after this install.

3) Install additional libraries:

sudo pip3 install numpy pillow spidev requests

4) Get app sources:

git clone https://github.com/dmitryelj/RPi-P2000Receiver.git

Optionally, fill the capcodes list (can be found in internet).

Connect RTL-SDR dongle and run the app:

python3 /home/pi/Documents/RPi-P2000Receiver/p2000.py

Add app to startup (sudo nano /etc/rc.local):

python3 /home/pi/Documents/RPi-P2000Receiver/p2000.py &

Thats it.

# Install (Windows)

Download and install Python 3

Install additional components: pip.exe install Pillow tzlocal requests numpy

Download and install RTL-SDR libraries (rtl-fm is required to be installed)

Clone as zip and extract app sources from this page

Optionally, fill the capcodes list (can be found in internet)

Run the app: C:\Python3\python.exe p2000.py 

# Get/Post support (optional) 

To get messages in a JSON format, http://IP-ADDRESS:8000/api/messages request can be used.

To get messages via websocket, use ws://IP-ADDRESS:8001 (see index.html for details).

To post data to a 3rd-party server, "postToServer" method should be uncommented in 'p2000.py'. 
