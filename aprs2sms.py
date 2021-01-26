#!/usr/bin/python
# encoding=utf8

import json
import re
import requests
import MySQLdb
import unidecode


db = MySQLdb.connect(host="localhost",  # host
                     user="root",       # username
                     passwd="",         # password
                     db="aprssms",      # database
                     use_unicode=True,  # Soporte a unicode
                     charset="utf8")    # charset utf-8


'''
Script to parse messages on the APRS network and catch the
ones with the call SMSCO.
This will parse the message field to extract the destination number and
the message, then proceed to send via SMS API

Requires a MySQL DB with wiht one table as follows


CREATE TABLE `packets` (
  `id` int(16) NOT NULL AUTO_INCREMENT,
  `callsign` varchar(32) DEFAULT '',
  `message` varchar(100) DEFAULT NULL,
  `duplicated` tinyint(8) DEFAULT NULL,
  `sent` tinyint(8) DEFAULT NULL,
  `dst` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `sents` (`callsign`,`message`)
) ENGINE=InnoDB AUTO_INCREMENT=675434 DEFAULT CHARSET=latin1;


Runs every minute, not from CRON, but from a tmux os screen session like this

#!/bin/bash
for (( ; ; )) do
	./aprs2sms.py
	sleep 60
done

Quick and dirty, ugly code but for 30 minutes of work is not bad.

JD

HK5ZVU - Jan 25 - 2021


'''


'''
This function sends the SMS using the hablame.co API, if using other
API need to me modified.
'''
def send_sms(callsign, recipient, message):
    print "-> send_sms"
    message = "Via SMSCO:" + callsign + ":" + message
    data = {
    'account': '', # Account ID
    'apiKey': '',  # API Key
    'token': '',   # Token
    'toNumber': recipient,
    'sms': message
    }

    response = requests.post('https://api101.hablame.co/api/sms/v2.1/send/', data=data)



'''
We pull the data from the APRS network using the aprs.fi API, parameters are 
defined here.
dst is the destination we are monitoring, in this case 'smsco'
'''
params = (
    ('what', 'msg'),
    ('dst', 'SMSCO'),
    ('apikey', ''),      # APRS api Key
    ('format', 'json'),
)

'''
Here we collect the data and do some basic validation to see if it´s valid.
'''
def check_aprs_data():
    response = requests.get('https://api.aprs.fi/api/get', params=params)
    json_data = json.loads(response.text)

    entries = json_data['entries']
    print "---"
    for entry in entries:
        try:
            sms = re.findall(
                "(\d{10})",
                entry["message"])
        except:
            sms = "None"

            print "---"
        if not sms:
            print "Skipping message ID: " + entry["messageid"]
            print "Reason: BAD format, no sms recipient"
        else:
            message = entry["message"].strip(sms[0])
            message = unidecode.unidecode(message)
            print "Packet: [ " + entry["srccall"] + " : " + str(sms[0]) + " : " + message + " : " + entry["messageid"] + " :  " + entry["time"] + " ]"

            mdst = str(sms[0])

            cur = db.cursor()
            sql = 'INSERT INTO packets(callsign, message, duplicated, sent, dst) \
             VALUES("%s", "%s", "%s", "%s", "%s")'
            try:
                cur.execute(sql, (entry["srccall"], message, 0, 0, mdst))
                db.commit()
                print cur._last_executed
            except:
                print 'Err'

            db.commit()
            print "---"

'''
APRS tends to duplicate packets, here we try to find the unique packets that are new.
Mostly to debug in case of issues
'''
def parse_unique_aprs():
    cur = db.cursor()
    sql = "select DISTINCT callsign, message, dst from aprssms.packets where sent = 0"
    cur.execute(sql)
    info = cur.fetchall()
    print "Query: [ " + cur._last_executed + " ]"
    for i in info:
        print "---"
        print i
    cur.close()
    print "---"
    return info

'''
Here, we pick the single packet and get the data to send the SMS
'''
def aprs_pick(unique):
    print "-> aprs_pick"
    print unique
    uniq = unique
    cur = db.cursor()
    message = "%" + uniq[1] + "%"
    callsign = str("%" + uniq[0] + "%")
    dst = str("%" + uniq[2] + "%")
    message = message.replace("\'", "")
    mcall = uniq[0]
    mcall = mcall.replace("\'", "")
    callsign = callsign.replace("\'", "")
    dst = dst.replace("\'", "")
    sql = "select id, callsign, dst, message from aprssms.packets where message LIKE %s AND callsign like %s and dst like %s limit 1"
    try:
        cur.execute(sql, (message, callsign, dst, ))
        print "Query: [ " + cur._last_executed + " ]"
        infor = cur.fetchall()

        jthis = infor[0]

        message = str(jthis[3].replace("\'", "")
                      )
        dst = str(jthis[2].replace("\'", "")
                  )
        mmessage = message.strip()
        callsign = callsign.strip()
        mdst = dst.strip()
        print "--- sending sms!"
        send_sms(mcall, mdst, mmessage)

        for i in infor:
            update_packet_state(i[0])
        cur.close()
    except:
        print "Err aprs_pick"
    print "<- aprs_pick"

'''
Here we check if there's something in queue to be sent
'''
def aprs_check_if_send(unique):

    for uniq in unique:

        cur = db.cursor()

        message = "%" + uniq[1] + "%"
        callsign = str("%" + uniq[0] + "%")
        dst = str("%" + uniq[2] + "%")
        message = message.replace("\'", "")
        callsign = callsign.replace("\'", "")
        dst = dst.replace("\'", "")
        sql = "select id, callsign, dst, message from aprssms.packets where message LIKE %s AND callsign like %s and dst like %s and sent = 1 limit 1"
        try:
            cur.execute(sql, (message, callsign, dst, ))
            print "Query: [ " + cur._last_executed + " ]"
            infor = cur.fetchall()
            item = infor[0]
            if item[0] != "":
                print "---"
                print item
                print "---"
                print 'already sent!'

        except:
            print "--> Need to send this!"
            print "---"
            print uniq
            print "---"
            aprs_pick(uniq)
            print "--- Sent!"

'''
Here we mark as SENT, to avoid duplicates
'''
def update_read(message, callsign, dst):
    print "*** in update_read"
    cur = db.cursor()
    sql = """select id, callsign, dst, message from aprssms.packets where message LIKE %s AND callsign like %s and dst like %s and sent = 0"""
    cur.execute(sql, (message, callsign, dst, ))
    infor = cur.fetchall()
    for info in infor:
        mid = info[0]
        print mid
        update_packet_state(info[0])

    db.commit()
    print "*** out update_read"


def update_packet_state(id):
    curi = db.cursor()
    sql = """update packets set sent = %s where id = %s"""
    data = ('1', id)
    curi.execute(sql, data)
    db.commit()

'''
When everything is completed, and before leaving, we mark everything as SENT
'''
def update_all_packets():
    print "*** in update_all_packetspackets"
    curi = db.cursor()
    sql = """update packets set sent = %s"""
    data = ('1', )
    curi.execute(sql, data)
    db.commit()
    print "*** out update_packet_state"


print "-> check_aprs_data "
message = check_aprs_data()
print "<- check_aprs_data "

print "-> parse_unique_aprs"
unique = parse_unique_aprs()
print "<- parse_unique_aprs"

print "-> aprs_check_if_send"
aprs_check_if_send(unique)
print "<- aprs_check_if_send"

print "Done!"

