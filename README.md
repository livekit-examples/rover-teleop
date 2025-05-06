# Raspberry Pi Rover Teleop

This project demostrates using LiveKit to enable tele-operation of a robot rover.  This repo includes the source code that runs on the rover for streaming realtime video to LiveKit and receiving control messages via LiveKit.  It also includes a Flutter app for remote teleop user for controlling the rover with a gamepad.

## Rover

The rover is built with all off-the-shelf components costing less than $200 USD.  This does not include the gamepad used by controller app.

1. [Raspberry Pi 4B 8GB](https://www.sparkfun.com/raspberry-pi-4-model-b-8-gb.html) - $75
2. [Raspberry Pi Camera V2](https://www.amazon.com/Raspberry-Pi-Camera-Module-Megapixel/dp/B01ER2SKFS) - $12
3. [Waveshare Rover](https://www.amazon.com/Waveshare-Flexible-Expandable-Chassis-Multiple/dp/B0CF55LM6Q) - $99
4. [3x 18650 batteries](https://www.amazon.com/dp/B0CDRBR2M1) - ~$14
4. Assorted mounting hardware & jumper cables

Total cost = $200

### Rover Hardware Setup

1. Install batteries into rover.
2. Install the Raspberry Pi onto the mounting bracket.
3. Install the camera module onto the mounting bracket.
4. Install the camera/compute bracket onto the rover.
5. Connect 5V, ground, Uart TX/TX to the rover ESP32.

### Raspberry Pi OS Setup

Before setting up the rover teleop software, you need to prepare your Raspberry Pi.  

1. Install Raspberry Pi OS 64-bit (Bookworm):
   - Download the Raspberry Pi Imager from [raspberrypi.com/software](https://www.raspberrypi.com/software/).
   - Use the imager to install Raspberry Pi OS 64-bit (Bookworm) on your SD card.
   - Complete the initial setup process (create user, set timezone, connect to WiFi).
   - This repo assumes you are configuring the Pi to use the default user `pi`.

2. Enable required interfaces:
   Power up the Pi connected to a monitor, keyboard, and mouse to continue the setup.  It should boot directly into a GUI desktop environment.

   ```
   sudo raspi-config
   ```
   - Navigate to "Interface Options"
   - Enable SSH
   - Enable Serial port - but do not enable login shell on serial port.
   - Enable I2C
   - Enable SPI
   - Reboot when prompted or run `sudo reboot`

3. Disable booting into GUI interface
   ```
   sudo systemctl set-default multi-user.target
   ```

3. Set up the Raspberry Pi Camera v2:
   - Connect the camera module to the Raspberry Pi's camera port
   - Add the following to `/boot/firmware/config.txt`:
   ```
   sudo nano /boot/firmware/config.txt
   ```
   - Comment out the line that says:
   ```
   camera_auto_detect=1
   ```
   - Add the following line:
   ```
   dtoverlay=imx219,rotation=0
   ```
   - Save and reboot

4. Verify the camera is working:
   ```
   cam -l
   ```
   - You should see the detected camera listed

At this point, you should be able to ssh into the pi and do everything remotely.

### Install Dependencies

Install other dependencies that the rover apps require:

1. Install uv (modern Python package manager):
   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install Gstreamer
   ```
   sudo apt install -y gstreamer1.0-libcamera gstreamer1.0-tools \
   gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
   gstreamer1.0-plugins-ugly   gstreamer1.0-libav   gstreamer1.0-alsa
   ```

3. Install the LiveKit CLI
   ```
   curl -sSL https://get.livekit.io/cli | bash
   ```

### Rover App Setup

1. Clone this repository to your Raspberry Pi:
   ```
   cd ~
   git clone https://github.com/livekit-examples/rover-teleop.git
   cd rover-teleop
   ```

4. Copy `env.example` to `.env` and fill with your actual credentials:
   ```
   cp /home/pi/rover-teleop/env.example /home/pi/rover-teleop/rover/.env
   nano /home/pi/rover-teleop/rover/.env
   ```

   Add your actual values for:
   ```
   LIVEKIT_URL=<your LiveKit server URL>
   LIVEKIT_API_KEY=<your API Key>
   LIVEKIT_API_SECRET=<your API Secret>
   LIVEKIT_CONTROLLER_TOKEN=<You don't need this token just yet>
   ROOM_NAME=<your room name>
   ROVER_PORT=/dev/serial0
   ```

3. Run the installation script to create systemd services:
   ```
   sudo ./install-services.sh
   ```

   This script will:
   - Install the systemd service files
   - Enable the services to start at boot


### Service Management

Start services:
```
sudo systemctl start rover-cam-gstreamer.service
sudo systemctl start rover-cam-publish.service
sudo systemctl start rover-control.service
```

Check service status:
```
sudo systemctl status rover-cam-gstreamer.service
sudo systemctl status rover-cam-publish.service  
sudo systemctl status rover-control.service
```

Stop services:
```
sudo systemctl stop rover-cam-gstreamer.service
sudo systemctl stop rover-cam-publish.service
sudo systemctl stop rover-control.service
```

View logs:
```
sudo journalctl -u rover-cam-gstreamer.service
sudo journalctl -u rover-cam-publish.service
sudo journalctl -u rover-control.service
```

![image](https://github.com/user-attachments/assets/928cb096-c130-49b2-80d9-0584f37b33b1)

![image](https://github.com/user-attachments/assets/7059c73b-da3a-4b8f-b467-13c104cb60b0)

