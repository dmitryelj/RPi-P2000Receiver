P2000 rtl-based receiver for the Raspberry Pi

# Features

- Standalone P2000 messages receiving (RTL-SDR compatible receiver required)

- Work with or without LCD

- HTTP-server with browser access from any home device

- Capcodes phonebook (note: user should fill capcodes.txt before using)

- 5000 messages memory (can be increased in settings)

# Screenshots

![View](/screenshots/RPi_P2000.jpg)

![View](/screenshots/RPi_P2000_web.jpg)

# Install

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

sudo pip3 install numpy pillow spidev

4) Get app sources:

git clone https://github.com/dmitryelj/RPi-P2000Receiver.git

Optionally, fill the capcodes list (can be found in internet).

Connect RTL-SDR dongle and run the app:

python3 /home/pi/Documents/RPi-P2000Receiver/p2000.py

Add app to startup (sudo nano /etc/rc.local):

python3 /home/pi/Documents/RPi-P2000Receiver/p2000.py &

Thats it.


