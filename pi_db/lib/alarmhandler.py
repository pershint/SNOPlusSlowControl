#After the pi_list is parsed like a couchdb entry, this class is
#responsible for checking the Current values against alarm threhsolds.
#Uses an instance of the alarmserver.py class, as well as the couchdb utils,
#to post alarms and update the alarms database

#FIXME: need logging added.  Will also want to add in an alarmposter instance?
# Or have it done in main, and pass returns to the AlarmPoster from returns on
#methods?

class AlarmHandler(object):
    '''This class is responsible for checking PIDB data against the
    alarm thresholds in the channel database, and updating the alarms
    dictionary.  This class also contains methods for using the given
    couchutils class to update the alarms in the alarms database.'''
    def __init__(self,pi_list,PIDBCouchConn):
        self.pi_list = pi_list
        self.PICouchConn = PIDBCouchConn
        #TODO: Have the PIDBCouchConn get the most recent channeldb and
        #Alarms?  Or should this be done in main.py, and fed in?

    #Compares pi_data to channeldb alarm parameters
    def checkThresholdAlarms(pi_data, channeldb, alarms):
        alarms_last = alarms
        alarms = {}
        alarms_dict = {}
        alarms_dict["timestamp"] = int(time.time())
        alarms_dict["sudbury_time"] = unix_to_human(alarms_dict["timestamp"])
        alarms_dict["version"] = version
        for name in pi_list:
            alarms[name["dbname"]] = [0]*len(name["channels"])
            alarms_dict[name["dbname"]] = []
        for channel in channeldb["deltav"]:
            dbname = channel["type"]
            chn_number = channel["id"]-1
            chn_value = pi_data[dbname]["values"][chn_number]
            isEnabled = 0
            try:
                isEnabled = channel["isEnabled"]
            except:
                isEnabled = 0
            if isEnabled>0:
                if chn_value<channel["lolo"] or chn_value>channel["hihi"]:
                    alarms[dbname][chn_number] = 2
                elif chn_value<channel["lo"] or chn_value>channel["hi"]:
                    alarms[dbname][chn_number] = 1
                if chn_value =="N/A":
                    alarms[dbname][chn_number] = 0
            isAlarm = 0
            this_alarm ={}
            if alarms_last:
                if alarms[dbname][chn_number]>0 and alarms_last[dbname][chn_number]>0:
                    isAlarm = 1
                    if alarms[dbname][chn_number]==1:
                        this_alarm["reason"] = "alarm"
                    if alarms[dbname][chn_number]==2:
                        this_alarm["reason"] = "action"
            if isAlarm>0:
                this_alarm["channel"] = chn_number
                this_alarm["value"] = chn_value
                this_alarm.update(channel)
                del this_alarm["isEnabled"]
                del this_alarm["multiplier"]
                alarms_dict[dbname].append(this_alarm)
        return alarms, alarms_dict
    
    #Clears all alarms for all entries in the channel database 
    def clearAllAlarms(channeldb):
        for channel in channeldb["deltav"]:
            channel_id = None
            try:
                channel_id = channel["alarmid"]
            except KeyError:
                #Entry does not have an alarmid. Ignore
                pass
            if channel_id is not None:
                clear_alarm(channel_id)       
    
    #Posts any alarms to the Alarm Server, clears items no longer alarming
    def PostAlarmServerAlarms(alarms_dict,alarms_last):
        #only check alarms_dict entries associated with databases
        nowalarming = []    
        aldict_entries = []
        for item in pi_list:
            aldict_entries.append(item["dbname"])
        for entry in aldict_entries:
            for channel in alarms_dict[entry]:
     	    if (((channel["reason"] == "action") or (channel["reason"] == "alarm")) and \
                       channel["alarmid"] is not None):
                   try:
    	           post_alarm(channel["alarmid"])
                       nowalarming.append(channel["alarmid"])
                   except Exception:
                       logging.exception('channel: %s\nKeyError' % (channel))
        #If a past alarm is not in the current alarms, clear alarms on that component
        counter = 0
        while counter < 3:
            try:
        	    for entry in aldict_entries:  #Loop through PI channel sets
                    if entry in alarms_last.keys():  
                        for past_alarm in alarms_last[entry]: #loop over PI channels' past alarms
                            try:
                                if (past_alarm["alarmid"] not in nowalarming):
                                    clear_alarm(past_alarm["alarmid"])
                            except Exception:
                                logging.exception('this_alarm: %s\nKeyError' % (this_alarm))
                return
            except:
                logging.info("Alarms Last likely empty from a connection error." + \
                     " Trying to get Alarms last from database...")
                counter+=1
                alarms_last = getPastAlarms()
                continue
        logging.exception("Could not clear alarms because could not" + \
               "Access the last alarms from couchdb.") 
        
    
    
    #Sends alarms email
    def printAlarms(alarms_dict,alarms_last):
        title = "DeltaV Alarms at " + time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(alarms_dict["timestamp"])) + "\n\n"
        old_list = []
        new_list = []
        new_alarm_dict = {}
        for machine in pi_list:
            dbname = machine["dbname"]
            if alarms_last != {}:
                 for alarm_num in range(len(alarms_last[dbname])):
                      channel_id = str(alarms_last[dbname][alarm_num]["id"])
                      channel_type = str(alarms_last[dbname][alarm_num]["type"]) 
                      channel_signal = str(alarms_last[dbname][alarm_num]["signal"])
                      old_list.append(channel_type+"-"+channel_id+" ("+channel_signal+")")
            for alarm_num in range(len(alarms_dict[dbname])):
                 channel_id = str(alarms_dict[dbname][alarm_num]["id"])
                 channel_type = str(alarms_dict[dbname][alarm_num]["type"]) 
                 channel_signal = str(alarms_dict[dbname][alarm_num]["signal"])
                 new_list.append(channel_type+"-"+channel_id+" ("+channel_signal+")")
                 msg = channel_type + "-" + channel_id + " (" + channel_signal + ")\n"
                 unit = alarms_dict[dbname][alarm_num]["unit"]
                 reason = alarms_dict[dbname][alarm_num]["reason"]
                 hi = "hi"
                 lo = "lo"
                 if reason =="action":
                      hi = "hihi"
                      lo = "lolo"
                 msg = msg + "Signal: " + str(alarms_dict[dbname][alarm_num]["value"]) + " " + unit
                 msg = msg + " outside " + reason + " limits of " + str(alarms_dict[dbname][alarm_num][lo]) + " " + unit
                 msg = msg + " to " + str(alarms_dict[dbname][alarm_num][hi]) + " " + unit + "\n\n"
                 new_alarm_dict[channel_type+"-"+channel_id+" ("+channel_signal+")"] = msg
        constant_alarms = set(old_list) & set(new_list)
        new_alarms = set(new_list) - set(old_list)
        no_longer_alarms = set(old_list) - set(new_list)
        super_msg = title
        if new_alarms != set([]):
             super_msg = super_msg + "New Alarms:" + "\n\n"
             for x in new_alarms:
                  super_msg = super_msg + new_alarm_dict[x]
        if no_longer_alarms != set([]):
             super_msg = super_msg + "No longer Alarms:" + "\n\n"
             for z in no_longer_alarms:
                  super_msg = super_msg + z + "\n\n"
        if constant_alarms != set([]):
             super_msg = super_msg + "Constant Alarms:" + "\n\n"
             for y in constant_alarms:
                  super_msg = super_msg + new_alarm_dict[y]
        if super_msg != title:
             sendMail("Alarms at " + time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(alarms_dict["timestamp"])), super_msg)
    
