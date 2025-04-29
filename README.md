# Raspberry Pi Rover Teleop

This project demostrates the use of LiveKit in conbination with a low cost robot rover platform running a Raspberry Pi 4B to enable low-latency video streaming from an onboard MIPI camera tele-operated from a desktop app with a bluetooth controller.

## Hardware used

The following is a list of components used in this project:

1. [Raspberry Pi 4B 8GB](https://www.sparkfun.com/raspberry-pi-4-model-b-8-gb.html?src=raspberrypi) - $75
2. [Raspberry Pi Camera V2](https://www.amazon.com/Raspberry-Pi-Camera-Module-Megapixel/dp/B01ER2SKFS) - $12

## Raspberry Pi OS Setup

Before setting up the rover teleop software, you need to prepare your Raspberry Pi:

1. Install Raspberry Pi OS 64-bit (Bookworm):
   - Download the Raspberry Pi Imager from [raspberrypi.com/software](https://www.raspberrypi.com/software/)
   - Use the imager to install Raspberry Pi OS 64-bit (Bookworm) on your SD card
   - Complete the initial setup process (create user, set timezone, connect to WiFi)

2. Enable required interfaces:
   ```
   sudo raspi-config
   ```
   - Navigate to "Interface Options"
   - Enable UART
   - Enable I2C
   - Enable SPI
   - Enable Camera
   - Reboot when prompted or run `sudo reboot`

3. Set up the Raspberry Pi Camera v2:
   - Connect the camera module to the Raspberry Pi's camera port
   - Add the following to `/boot/firmware/config.txt`:
   ```
   sudo nano /boot/firmware/config.txt
   ```
   - Add these lines at the end of the file:
   ```
   # Enable camera
   dtoverlay=imx219
   start_x=1
   gpu_mem=128
   ```
   - Save and exit (Ctrl+X, then Y, then Enter)
   - Reboot the Raspberry Pi:
   ```
   sudo reboot
   ```

4. Verify the camera is working:
   ```
   libcamera-hello --timeout 5000
   ```
   - You should see the camera feed for 5 seconds
   - If not working, check connections and run `vcgencmd get_camera` to verify detection

## Setup Instructions

1. Clone this repository to your Raspberry Pi:
   ```
   git clone https://github.com/livekit-examples/rover-teleop-services.git
   cd rover-teleop-services
   ```

2. Make the installation script executable:
   ```
   chmod +x install-services.sh
   ```

3. Run the installation script (requires sudo):
   ```
   sudo ./install-services.sh
   ```

   This script will:
   - Clone the rover-teleop repository to `/home/pi/rover-teleop` if it doesn't exist
   - Install uv (modern Python package manager) if not already installed
   - Install Python dependencies using uv
   - Create a template `.env` file if it doesn't exist
   - Install the LiveKit CLI if it's not already installed
   - Install the systemd service files
   - Enable the services to start at boot

4. Edit the `.env` file with your actual credentials:
   ```
   sudo nano /home/pi/rover-teleop/.env
   ```

   Add your actual values for:
   ```
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   LIVEKIT_URL=your_livekit_url
   ROOM_NAME=your_room_name
   ROVER_PORT=/dev/ttyUSB0  # Adjust based on your rover's serial port
   ```

## Service Management

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

## Manual Setup (if needed)

If you prefer to set up the environment manually:

1. Clone the repository:
   ```
   git clone https://github.com/livekit/examples.git
   cp -r examples/rover-teleop ~/
   rm -rf examples
   ```

2. Install uv (modern Python package manager):
   ```
   curl -sSf https://raw.githubusercontent.com/astral-sh/uv/main/install.sh | bash
   ```

3. Install Python dependencies with uv:
   ```
   cd ~/rover-teleop
   uv pip install -r rover/requirement.txt
   uv pip install python-dotenv livekit
   ```

4. Install LiveKit CLI:
   ```
   curl -sSL https://get.livekit.io | bash
   ```

5. Create a `.env` file:
   ```
   cd ~/rover-teleop
   cp .env.example .env  # If example exists
   nano .env             # Edit with your values
   ```

## About uv

This project uses [uv](https://github.com/astral-sh/uv), a modern Python package manager and alternative to pip/venv that offers:

- Significantly faster package installation and dependency resolution
- Global isolation of packages without virtual environments
- Compatible with pip requirements files
- Built-in Python interpreter management
- Improved reliability and reproducibility

Learn more at [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv).
