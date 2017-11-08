import os
import json
from datetime import datetime



class ArNotableLogger(object):
    """
    Some details for later
    Right now this class tries to simplify
    the parsing of events and configs from Splunk mod modular_alert
    format them in a way Splunk ES understands and send them to HEC
    """

    # LOGGING FORMAT

    def __init__(self, lambda_context, lambda_event):
        """Set up our HEC instance using environment
        variables from the lambda function we are running under
        and set up our log line examples"""

        self.LOG_STRING = '{date} {loglevel} sendmodaction - signature="{sig}" action_name="{lambda_name}" search_name="{searchname}" sid="{orig_sid}" rid="{rid}" app="{app}" user="{splk_user}" action_mode="lambda" action_status="{status}"'
        self.UI_STRING = '{date} {loglevel} sendmodaction - signature="Invoking modular action" action_name="{lambda_name}" search_name="{searchname}" sid="{orig_sid}" rid="{rid}" app="{app}" user="{splk_user}" action_mode="lambda" action_status="{status}"'

        self.sourcetype = 'modular_alerts:{}'.format(lambda_context.function_name)
        self.source = '{}_modalert.log'.format(lambda_context.function_name)




        # store lambda context internally
        self.lambda_context = lambda_context
        # pull in our event and save it internally
        # as the mod alert config and event
        ar_event = lambda_event['event_payload']
        ar_config = lambda_event['config_payload']

        # determine if event was run 'ad-hoc' or 'saved search'
        # from the splnk event and config from the mod-action
        self.ar_event = json.loads(ar_event)
        self.ar_config = json.loads(ar_config)
        if 'orig_sid' in self.ar_event:
            self.sid = self.ar_event['orig_sid']
            self.srch_name = self.ar_event['search_name']
        else:
            self.sid = self.ar_config['sid']
            self.srch_name = self.ar_config['search_name']

        if 'user' in self.ar_config:
            self.user = self.ar_config['user']
        else:
            self.user = self.ar_config['owner']

    def writebase(self, ar_status, action_name=None):
        """Sends the requried message to Splunk to register
        in the ES UI"""
        t = datetime.utcnow()
        s = t.strftime('%Y-%m-%d %H:%M:%S,%f')
        log_time = s[:-3] + "+0000"
        if action_name is None:
            action_name = self.lambda_context.function_name
        try:
            print self.UI_STRING.format(date=log_time, loglevel='INFO', lambda_name=action_name, \
                                              searchname=self.srch_name, orig_sid=str(self.sid),
                                              rid=str(self.ar_event['rid']), \
                                              app=self.ar_config['app'], splk_user=self.user, status=ar_status)
        except Exception as e:
            print "Encountered exception while attempting to write base data: {}".format(str(e))

    def writecustom(self, message, ar_status):
        """"""
        t = datetime.utcnow()
        s = t.strftime('%Y-%m-%d %H:%M:%S,%f')
        log_time = s[:-3] + "+0000"
        try:
            print self.LOG_STRING.format(date=log_time, loglevel='INFO', sig=message,
                                               lambda_name=self.lambda_context.function_name, \
                                               searchname=self.srch_name, orig_sid=str(self.sid),
                                               rid=str(self.ar_event['rid']), \
                                               app=self.ar_config['app'], splk_user=self.user, status=ar_status)

        except Exception as e:
            print "Encountered exception while attempting to write custom data: {}".format(str(e))

    def _sendcustomtest(self, message, ar_status):
        """"""
        t = datetime.utcnow()
        s = t.strftime('%Y-%m-%d %H:%M:%S,%f')
        log_time = s[:-3] + "+0000"
        print ":::TEST:::" + self.LOG_STRING.format(date=log_time, loglevel='INFO', sig=message,
                                                    lambda_name=self.lambda_context.function_name, \
                                                    searchname=self.srch_name, orig_sid=str(self.sid),
                                                    rid=str(self.ar_event['rid']), \
                                                    app=self.ar_config['app'], splk_user=self.user, status=ar_status)

    def _sendbasetest(self, ar_status):
        """Sends the requried message to Splunk to register
        in the ES UI"""
        t = datetime.utcnow()
        s = t.strftime('%Y-%m-%d %H:%M:%S,%f')
        log_time = s[:-3] + "+0000"
        print ":::TEST:::" + self.UI_STRING.format(date=log_time, loglevel='INFO',
                                                   lambda_name=self.lambda_context.function_name, \
                                                   searchname=self.srch_name, orig_sid=str(self.sid),
                                                   rid=str(self.ar_event['rid']), \
                                                   app=self.ar_config['app'], splk_user=self.user, status=ar_status)





