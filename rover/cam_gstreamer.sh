# create a gstreamer pipeline to publish the camera stream to a tcp sink server on port 5004
gst-launch-1.0 libcamerasrc ! \
    capsfilter caps=video/x-raw,width=640,height=480,format=NV12,interlace-mode=progressive ! \
    v4l2h264enc extra-controls="controls,repeat_sequence_header=1" ! 'video/x-h264,level=(string)4' ! \
    h264parse config-interval=1 ! \
    queue ! \
    tcpserversink host=127.0.0.1 port=5004