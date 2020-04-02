#-*- coding:utf-8 -*-

DEBUG = False

import os
import sys
import struct
import bluetooth._bluetooth as bluez
import math
import time
import paho.mqtt.client as mqtt
import json
from threading import Thread

#mqtt = mqtt.Client("python_pub")
#mqtt.connect("192.168.0.20",1883)

LE_META_EVENT = 0x3e
LE_PUBLIC_ADDRESS=0x00
LE_RANDOM_ADDRESS=0x01
LE_SET_SCAN_PARAMETERS_CP_SIZE=7
OGF_LE_CTL=0x08
OCF_LE_SET_SCAN_PARAMETERS=0x000B
OCF_LE_SET_SCAN_ENABLE=0x000C
OCF_LE_CREATE_CONN=0x000D

LE_ROLE_MASTER = 0x00
LE_ROLE_SLAVE = 0x01

# these are actually subevents of LE_META_EVENT
EVT_LE_CONN_COMPLETE=0x01
EVT_LE_ADVERTISING_REPORT=0x02
EVT_LE_CONN_UPDATE_COMPLETE=0x03
EVT_LE_READ_REMOTE_USED_FEATURES_COMPLETE=0x04

# Advertisment event types
ADV_IND=0x00
ADV_DIRECT_IND=0x01
ADV_SCAN_IND=0x02
ADV_NONCONN_IND=0x03
ADV_SCAN_RSP=0x04

recvData = ""
client = ""
cx = 0.0
cy = 0.0

class KalmanFilter:
    cov=float('nan')
    x=float('nan')
    
    def __init__(self, R, Q):
        '''
        Constructor
        :param R: Process Noise
        :param Q: Measurement Noise
        '''
        
        self.A=1
        self.B=0
        self.C=1
        
        self.R=R
        self.Q=Q
        
    def filter(self, measurement):
        '''
        Filters a measurement
        :param measurement: The measurement value to be filtered
        :return: the filtered value
        '''
        
        u=0
        if math.isnan(self.x):
            self.x=(1/self.C)*measurement
            self.cov=(1/self.C)*self.Q*(1/self.C)
        else:
            predX=(self.A*self.x)+(self.B*u)
            predCov=((self.A*self.cov)*self.A)+self.R
            
            # Kalman Gain
            K=predCov*self.C*(1/((self.C*predCov*self.C)+self.Q))
            
            # Correction
            self.x=predX+K*(measurement-(self.C*predX))
            self.cov=predCov-(K*self.C*predCov)
            
        return self.x
    
    def last_measurement(self):
        '''
        Returns the last measurement fed into the filter
        :return: The last measurement fed into the filter
        '''
        
        return self.x
    
    def set_measurement_noise(self, noise):
        '''
        Sets measurement noise
        :param noise: The new measurement noise
        '''
        
        self.Q=noise
        
    def set_process_noise(self, noise):
        '''
        Sets process noise
        :param noise: The new process noise
        '''
        
        self.R=noise
        
        
def on_connect(client, userdata, flags, rc):
    print("connected with result code " + str(rc))
    client.subscribe("ilovecat")

def on_message(client, userdata, msg):
    global cx
    global cy
    recvData = str(msg.payload)
    jsonData = json.loads(recvData)
    print("catx :" + str(jsonData["catx"]))
    print("caty :" + str(jsonData["caty"]))
    cx = float(str(jsonData["catx"]))
    cy = float(str(jsonData["caty"]))


def mqtt_sub():
    global client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("192.168.1.2",1883,60) #cat ip
    client.loop_forever()




def returnnumberpacket(pkt):
    myInteger = 0
    multiple = 256
    for c in pkt:
        myInteger +=  struct.unpack("B",c)[0] * multiple
        multiple = 1
    return myInteger 

def returnstringpacket(pkt):
    myString = "";
    for c in pkt:
        myString +=  "%02x" %struct.unpack("B",c)[0]
    return myString 

def printpacket(pkt):
    for c in pkt:
        sys.stdout.write("%02x " % struct.unpack("B",c)[0])

def get_packed_bdaddr(bdaddr_string):
    packable_addr = []
    addr = bdaddr_string.split(':')
    addr.reverse()
    for b in addr: 
        packable_addr.append(int(b, 16))
    return struct.pack("<BBBBBB", *packable_addr)

def packed_bdaddr_to_string(bdaddr_packed):
    return ':'.join('%02x'%i for i in struct.unpack("<BBBBBB", bdaddr_packed[::-1]))

def hci_enable_le_scan(sock):
    hci_toggle_le_scan(sock, 0x01)

def hci_disable_le_scan(sock):
    hci_toggle_le_scan(sock, 0x00)

def hci_toggle_le_scan(sock, enable):
    cmd_pkt = struct.pack("<BB", enable, 0x00)
    bluez.hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)


def hci_le_set_scan_parameters(sock):
    old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    SCAN_RANDOM = 0x01
    OWN_TYPE = SCAN_RANDOM
    SCAN_TYPE = 0x01

def solEqP(a, b, c, beforeN):
    D=b*b-4*a*c
    if D>=0:
        return (-b+D**0.5)/2*a
    else:
        return beforeN

def solEqM(a, b, c, beforeN):
    D=b*b-4*a*c
    if D>=0:
        return (-b-D**0.5)/2*a
    else:
        return beforeN

def tri_survey(r1, r2, r3, d1, d2, d3, beforex, beforey):
    if r1>1.2 or r2>0.9 or r3>1.5:
        return beforex, beforey
    x, y=0, 0
    if r1+r2>d1 and r1+r3>d2 and r2+r3>d3:
        if r3<max(d3+r2, d2+r1) and r2<max(d3+r3, d1+r1) and r1<max(d1+r2, d2+r3):
            x=(pow(r1,2)-pow(r2,2)+pow(d1,2))/(2*d1)
            y=(pow(r1,2)-pow(r3,2)+pow(d2,2))/(2*d2)
        elif r3>max(d3+r2, d2+r1) and r2<max(d3+r3, d1+r1) and r1<max(d1+r2, d2+r3):
            x=(pow(r1,2)-pow(r2,2)+pow(d1,2))/(2*d1)
            if pow(r1,2)-pow(x,2)<0:
                x=beforex
                y=beforey
            else:    
                y=-math.sqrt(pow(r1,2)-pow(x,2))
        elif r3<max(d3+r2, d2+r1) and r2>max(d3+r3, d1+r1) and r1<max(d1+r2, d2+r3):
            y=(pow(r1,2)-pow(r3,2)+pow(d2,2))/(2*d2)
            if pow(r1,2)-pow(y,2)<0:
                x=beforex
                y=beforey
            else:
                x=-math.sqrt(pow(r1,2)-pow(y,2))
        elif r3<max(d3+r2, d2+r1) and r2<max(d3+r3, d1+r1) and r1>max(d1+r2, d2+r3):                    
            A=(r3**2-r3**2-d1**2-d2**2)/2*d2
            x=solEqP(1+d1**2/d2**2, 2*d1*A/d2, A**2-r3**2, beforex)
            B=(r2**2-r3**2-d1**2-d2**2)/2*d1
            y=solEqP(1+d2**2/d1**2, 2*d2*B/d1, B**2-r2**2, beforey)
        else:
            x=beforex
            y=beforey
    elif r1+r2<d1 and r1+r3>d2 and r2+r3<d3:
        y=(pow(r1,2)-pow(r3,2)+pow(d2,2))/(2*d2)
        if pow(r1,2)-pow(y,2)<0:
            x=beforex
            y=beforey
        else:
            x=math.sqrt(pow(r1,2)-pow(y,2))
    elif r1+r2>d1 and r1+r3<d2 and r2+r3<d3:
        x=(pow(r1,2)-pow(r2,2)+pow(d1,2))/(2*d1)
        if pow(r1,2)-pow(x,2)<0:
            x=beforex
            y=beforey
        else:
            y=math.sqrt(pow(r1,2)-pow(x,2))
    elif r1+r2<d1 and r1+r3<d2 and r2+r3>d3:
        A=(r3**2-r3**2-d1**2-d2**2)/2*d2
        x=solEqM(1+d1**2/d2**2, 2*d1*A/d2, A**2-r3**2, beforex)
        B=(r2**2-r3**2-d1**2-d2**2)/2*d1
        y=solEqM(1+d2**2/d1**2, 2*d2*B/d1, B**2-r2**2, beforey)
    else:
        x=beforex
        y=beforey
    
    return x, y
                   
sumval1, sumval2, sumval3 = 0, 0, 0
cnt1, cnt2, cnt3 = 0, 0, 0
truval1, truval2, truval3=0,0,0

def parse_events(sock, loop_count=150):
    global client
    old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
    flt = bluez.hci_filter_new()
    bluez.hci_filter_all_events(flt)
    bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )
    done = False
    results = []
    myFullList = []
    r1 = 0
    r2 = 0
    r3 = 0
    d1 = 1.2 # beacon 1, 2 distance
    d2 = 0.9 # beacon 1, 3 distance
    d3 = math.sqrt(pow(d1, 2)+pow(d2, 2)) # beacon 2, 3 distance
    towerx = 0.0
    towery = 0.0
    kalmanTest1=KalmanFilter(0.008,0.1)
    kalmanTest2=KalmanFilter(0.008,0.1)
    kalmanTest3=KalmanFilter(0.008,0.1)
    
    global sumval1, sumval2, sumval3
    global cnt1, cnt2, cnt3
    global truval1, truval2, truval3
    
    while True:
        pkt = sock.recv(255)
        ptype, event, plen = struct.unpack("BBB", pkt[:3])
        #print "--------------" 
        if event == bluez.EVT_INQUIRY_RESULT_WITH_RSSI:
            i =0
        elif event == bluez.EVT_NUM_COMP_PKTS:
            i =0 
        elif event == bluez.EVT_DISCONN_COMPLETE:
            i =0 
        elif event == LE_META_EVENT:
            
            
            subevent, = struct.unpack("B", pkt[3])
            pkt = pkt[4:]
            if subevent == EVT_LE_CONN_COMPLETE:
                le_handle_connection_complete(pkt)
            elif subevent == EVT_LE_ADVERTISING_REPORT:
                num_reports = struct.unpack("B", pkt[0])[0]
                report_pkt_offset = 0
                for i in range(0, num_reports):
		
                    macAd =  packed_bdaddr_to_string(pkt[report_pkt_offset + 3:report_pkt_offset + 9])

                        #b8:27:eb:be:33:f0 woozin_rasb
                        #b8:27:eb:55:62:5a case rasb
                        #b8:27:eb:bc:7a:92 nomal rasb
                        #b8:27:eb:11:46:8f seed pi

                        #arduino
                        #4c:24:98:5c:ce:58 03
                        #90:e2:02:b1:0b:a5 01
                        #90:e2:02:be:ec:18 02

                    if macAd == "4c:24:98:5c:ce:58" or  macAd == "90:e2:02:b1:0b:a5" or macAd == "90:e2:02:be:ec:18" :


                        print ("-------------")
                        txpower, = struct.unpack("b", pkt[report_pkt_offset -2])
                    	# #print "\ttxpower:", txpower
	
                        rssi, = struct.unpack("b", pkt[report_pkt_offset -1])
                    	# #print "\tRSSI:", rssi
                        #ratio = rssi*1.0/txpower
                                             
                        if macAd=="4c:24:98:5c:ce:58":
                            #print "rssi : ", rssi
                            rssiC1=kalmanTest1.filter(rssi)
                            #print "rssiC1 : ", rssiC1
                            #print "rssi : ", rssi
                            #print "txpower : " , txpower
                            ratio1=rssiC1*1.0/txpower
                            if ratio1>1.0:
                                r1=math.pow(ratio1, 10)
                            else:
                                temp=ratio1**(7.7095)
                                temp=temp*0.89976
                                r1=temp+0.111
                            sumval1 = sumval1 + r1
                            cnt1 = cnt1 + 1
                            #ratio=rssiC1*1.0/txpower
                            #print "rssiC1 : ", rssiC1
                        elif macAd=="90:e2:02:b1:0b:a5":
                            rssiC2=kalmanTest2.filter(rssi)
                            ratio2=rssiC2*1.0/txpower
                            if ratio2>1.0:
                                r2=math.pow(ratio2, 10)
                            else:
                                temp=ratio2**(7.7095)
                                temp=temp*0.89976
                                r2=temp+0.111
                            sumval2 = sumval2 +r2
                            cnt2 = cnt2 + 1
                        elif macAd=="90:e2:02:be:ec:18":
                            rssiC3=kalmanTest3.filter(rssi)
                            ratio3=rssiC3*1.0/txpower
                            if ratio3>1.0:
                                r3=math.pow(ratio3, 10)
                            else:
                                temp=ratio3**(7.7095)
                                temp=temp*0.89976
                                r3=temp+0.111
                            sumval3=sumval3+r3
                            cnt3=cnt3+1
                        if cnt1==10:
                            cnt1=0
                            truval1=sumval1/10
                            sumval1=0
                        if cnt2==10:
                            cnt2=0
                            truval2=sumval2/10
                            sumval2=0
                        if cnt3==10:
                            cnt3=0
                            truval3=sumval3/10
                            sumval3=0
                            # 03 = r1(mid) , 01  = r2(right) , 02 = r3(left)

                        print "(truval1, truval2, truval3)=", truval1, " ", truval2, " ", truval3
                        if r1==0.0 or r2==0.0 or r3==0.0:
                            print ("No Beacon: ", r1," ", r2," ", r3)
                            
                        else :
                            cxp, cyp, txp, typ=0, 0, 0, 0

                            towerx, towery=tri_survey(truval1, truval2, truval3, d1, d2, d3, towerx, towery)
                            if cx>=0 and cx<d1/3:
                                cxp=0
                            elif cx>=d1/3 and cx<d1*2/3:
                                cxp=1
                            elif cx>=d1*2/3 and cx<=d1:
                                cxp=2
                            else:
                                cxp=3

                            if cy>=0 and cy<d2/3:
                                cyp=0
                            elif cy>=d2/3 and cy<d2*2/3:
                                cyp=1
                            elif cy>=d2*2/3 and cy<=d2:
                                cyp=2
                            else:
                                cyp=3

                            if towerx>=0 and towerx<d1/3:
                                txp=0
                            elif towerx>=d1/3 and towerx<d1*2/3:
                                txp=1
                            elif towerx>=d1*2/3 and towerx<=d1:
                                txp=2
                            else:
                                txp=3

                            if towery>=0 and towery<d2/3:
                                typ=0
                            elif towery>=d2/3 and towery<d2*2/3:
                                typ=1
                            elif towery>=d2*2/3 and towery<=d2:
                                typ=2
                            else:
                                typ=3

                            towerx = round(towerx, 4)
                            towery = round(towery, 4)
                            print "(X,Y) = (" ,towerx,",", towery, ")"
                            dis =math.sqrt(pow((towerx-cx),2) + pow((towery-cy),2))
                            MQTT_MSG=json.dumps({"distance":dis, "towerxloc":txp,
                                                 "toweryloc":typ, "catxloc":cxp,
                                                 "catyloc":cyp})
                            mqtt.publish("towerInfo", MQTT_MSG)
                done = True
    sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
    return myFullList

def blemain():
    dev_id = 0
    try:
        sock = bluez.hci_open_dev(dev_id)
        print "ble thread started"
    except:
        print "error accessing bluetooth device..."
        sys.exit(1)
    hci_le_set_scan_parameters(sock)
    hci_enable_le_scan(sock)

    while True:
        returnedList = parse_events(sock, 10)
        print "///////////"
        for beacon in returnedList:
            print beacon


if __name__ == "__main__":
    th1 = Thread(target=blemain, args=())
    th2 = Thread(target=mqtt_sub, args=())
    
    th2.start()
    th1.start()
    th2.join()
    th1.join()

