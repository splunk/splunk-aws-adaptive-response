def lambda_handler(event, context):
    import os
    import boto3
    import re
    import arlogger
    import json
    from botocore.exceptions import ClientError

    """

    Generic error handler. In the case of an action being rejected by email approver, this handler will cleanup 
    previous tags and snaps of the flagged instance.

    All error logging (except for in SnapEmail) occurs in this state.

    """

    event_payload = json.loads(event['event_payload'])
    config_payload = json.loads(event['config_payload'])
    config = config_payload["configuration"]

    hec = arlogger.ArNotableLogger(context, event)

    error = event["Error"]
    cause = event["Cause"]
    region = os.environ["region"]
    
    # Placeholder for logging portion
    if (error == "Rejected"):
        sids = list(event["sid"])
        instance_id = event["instance_id"]
        
        tag_key = "Flagged by Splunk"
        tag_value = "quarantine"
        try: 
            ec2 = boto3.resource(
                'ec2', 
                region_name=region)
            for sid in sids:
                snapshot = ec2.Snapshot(sid)
                response = snapshot.delete()
            instance = ec2.Instance(instance_id)
            tag = instance.delete_tags( 
                    Tags=[ { 'Key': tag_key, 'Value': tag_value } ])
                        
        except ClientError as e:
            hec.writebase("failure", "Cleanup failure: " + str(list(e)[0]))
            return
        hec.writebase("failure", "Action denied by user")
        hec.writebase("success", "Snapshot and tags deleted. Cleanup complete")
        return
    elif (error == "ClientError"):
        hec.writebase("failure", "An error occurred while a lambda function was running: " + str(cause))
        return
    elif (error == "Timeout"):
        hec.writebase("failure", "The step function timed out.")
        return
    else:
        hec.writebase("failure", str(cause))
        return