'''
Support for older MiLight/easybulb/LimitlessLED bulbs, four to a wifi hub. No
need for the custom ESP8266 bridge, this works with the original MiLight hub.
'''

from functions.colors import convert_xy, rgbBrightness

import binascii
import colorsys
import logging
import socket
import time

sock = None
lastSentMessageTime = 0


def set_light(light, data, rgb=None):
    for key, value in data.items():
        light.state[key] = value

    on = light.state["on"]
    if not on:
        sendOffCmd(light)
    if on:
        sendOnCmd(light)
        colormode = light.state["colormode"]
        if colormode == "xy":
            xy = light.state["xy"]
            if rgb:
                r, g, b = rgbBrightness(rgb, light.state["bri"])
            else:
                r, g, b = convert_xy(xy[0], xy[1], light.state["bri"])
            hue = rgbToMilight(r, g, b)
            sendHueCmd(light, hue)

        elif colormode == "ct":
            sendWhiteCmd(light)

        sendBrightnessCmd(light, (light.state["bri"] / 255) * 100)


def bytesToHexStr(b):
    hex_data = binascii.hexlify(b)
    return hex_data.decode('utf-8')


def sendMsg(light, msg):
    global sock
    logging.info("sending udp message to MiLight box:" + bytesToHexStr(msg))
    if sock is None:
        logging.info("creating socket")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        logging.info("connecting to ip")
        sock.connect((light.protocol_cfg["ip"], light.protocol_cfg["port"]))

    logging.info("sock.sendall")
    sock.sendall(msg)
    time.sleep(0.1)


def closeSocket():
    global sock, lastSentMessageTime
    if sock is not None:
        logging.info("force closing socket connection")
        sock.close()
    sock = None


def sendOnCmd(light, wait=True):
    group = light.protocol_cfg["group"]
    cmd = groupID(group).to_bytes(1, byteorder='big')
    cmd += b'\x00\x55'
    sendMsg(light, cmd)


def sendOffCmd(light):
    group = light.protocol_cfg["group"]
    if group == 0:
        sendMsg(light, b"\x41\x00\x55")
    else:
        sendMsg(light, (groupID(group) + 1).to_bytes(1, byteorder='big') + b"\x00\x55")


# brightness is between 0-100
def sendBrightnessCmd(light, brightness):
    sendOnCmd(light)
    cmd = b'\x4E'
    cmd += (2 + int(brightness / 4)).to_bytes(1, byteorder='big')
    cmd += b'\x55'
    sendMsg(light, cmd)


# hue is between 0-255
def sendHueCmd(light, hue):
    sendOnCmd(light)
    cmd = b'\x40'
    cmd += hue.to_bytes(1, byteorder='big')
    cmd += b'\x55'
    sendMsg(light, cmd)


def sendWhiteCmd(light):
    # No control over color temp, just white vs color with these lights
    group = light.protocol_cfg["group"]
    cmd = (groupID(group) + 0x80).to_bytes(1, byteorder='big')
    cmd += b'\x00\x55'
    sendMsg(light, cmd)


def get_light_state(light):
    return {}


def groupID(group):
    if group is 0:
        return 0x42
    else:
        return 67 + (2 * group)


def rgbToMilight(red, green, blue):
    '''
    This isn't quite right, and is full of magic numbers found by trial & error.
    We just extract the hue of the rgb colour and try to map that to the
    milight colour chart, ignoring saturation and value.
    '''
    hsv = colorsys.rgb_to_hsv(red, green, blue)
    hue = hsv[0] * 360
    milight = ((225 - hue) % 360) * 256 / 360
    return int(round(milight))
