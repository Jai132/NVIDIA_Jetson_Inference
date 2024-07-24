#!/bin/bash

# 1. connect to given ssid 
# 2. check if the ssid is correctly connected
# 3. launch webapp

echo "dheritage" | figlet

read_yaml() {
    local yaml_file="$1"
    local key="$2"
    grep "$key:" "$yaml_file" | awk -F ': ' '{print $2}'
}

check_wifi() {
    local SSID=$1
    if nmcli -t -f ACTIVE,SSID dev wifi | grep -q "^yes:$SSID$"; then
        echo "Connected to $SSID."
        return 0
    else
        echo "Not connected to $SSID. Checking again in 5 seconds..."
        connect_wifi "$SSID"
        return 1
    fi
}

connect_wifi() {
    local SSID=$1
    # Connect to the Wi-Fi network with the given SSID
    nmcli device wifi connect "$SSID"

    # Check the connection status
    if [ $? -eq 0 ]; then
        echo "Successfully connected to $SSID"
        return 0
    else
        echo "Failed to connect to $SSID"
        return 1
    fi
}

# Check if the first argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <mode: {mono_recorded, mono_webcam2, rgbd_recorded, rgbd_webcam}>"
    exit 1
fi

# Perform actions based on the selected mode
if [ "$1" = "mono_recorded" ]; then
    echo "MODE: monocular recorded mode"
    settingsFileName='test_recorded.yaml'
    settingsDirectory='ORB_SLAM3/Examples/Monocular/'
elif [ "$1" = "mono_webcam2" ]; then
    echo "MODE: monocular webcam2 mode"
    settingsFileName='test_webcam_2.yaml'
    settingsDirectory='ORB_SLAM3/Examples/Monocular/'
elif [ "$1" = "rgbd_recorded" ]; then
  echo "MODE: rgbd recorded mode"
  settingsFileName=''
  settingsDirectory='ORB_SLAM3/Examples/RGB-D/Setup_Files/'
elif [ "$1" = "rgbd_webcam" ]; then
  echo "MODE: rgbd webcam mode"
  settingsFileName='RealSense_D435i.yaml'
  settingsDirectory='ORB_SLAM3/Examples/RGB-D/Setup_Files/'
else
    echo "Invalid mode: $1"
    exit 1
fi

cd /home/vision/NVIDIA_Jetson_Inference/digital_heritage_project_demo_SLAM/

settingsDirectory=$settingsDirectory$settingsFileName

hostip=$(read_yaml "$settingsDirectory" hostip)
portNum=$(read_yaml "$settingsDirectory" portNum)
SSID=$(read_yaml "$settingsDirectory" SSID)

# Remove quotes from hostip and portNum
hostip="${hostip//\"/}"  # Remove double quotes
portNum="${portNum//\"/}"  # Remove double quotes
SSID="${SSID//\"/}"  # Remove double quotes
echo "Value of hostip is: $hostip"
echo "Value of portNum is: $portNum"
echo "Value of SSID is: $SSID"

while ! check_wifi "$SSID"; do
    sleep 5
done

hostAddr="$hostip:$portNum"

url="http://$hostAddr/"

echo "launch dheritage webapp"
cd Digital\ Heritage\ app/new_app/dheritage

python3 manage.py runserver $hostAddr
# xdg-open "$url"
