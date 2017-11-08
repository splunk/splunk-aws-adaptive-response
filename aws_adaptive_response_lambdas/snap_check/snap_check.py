def lambda_handler(event, context):
    import os
    import boto3
    import arlogger
    import json
    from botocore.exceptions import ClientError
    
    """

    Function for checking if snapshot/s have completed. Once all snapshot/s are complete, the fucntion will perform the requested action on the 
    instance. Also handles action email rejection.

    """


    # If the state prior to this one is the parallel email state, the input will be a list of all returns of the parallel state appended together. 
    # We extract both returns to handle errors in either state. When the state switches into this one from the wait state, the format will be a dict
    # instead of a list, so extraction is not needed.
    
    if (type(event) is not dict):
        status = event[1]
        event = event[0]

        if (status == "2"):
            config_payload = json.loads(event['config_payload'])
            config = config_payload["configuration"]
            return {"instance_id": config["instance_id"], "action": config["instance_action"], "sid": event["sid"], "ret_var": 2, "Cause": "Action was rejected.",
                "event_payload": event['event_payload'], "config_payload": event['config_payload'], "Error": "Rejected"}

    event_payload = json.loads(event['event_payload'])
    config_payload = json.loads(event['config_payload'])
    config = config_payload["configuration"]

    hec = arlogger.ArNotableLogger(context, event)

    i_id = config["instance_id"]
    action = config["instance_action"]
    snap_list = event["sid"]
    ret_var = event["ret_var"]

    region = os.environ["region"]

    # Check of previous state. Essentially a formality since failure in email state means email will never send and our activity will timeout before reaching here
    if (ret_var == 2):
        return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 3, "Cause": event["Cause"], "event_payload": event['event_payload'], "config_payload": event['config_payload'], "Error": event["Error"]}
    
    # list of snaps to be removed after loop
    to_remove = []
    
    for s_id in snap_list:
        try: 
            ec2 = boto3.resource(
                    'ec2', 
                    region_name=region)
                
            snapshot = ec2.Snapshot(s_id)
            progress_total = int(snapshot.progress[:-1])
                
            if progress_total == 100:
                to_remove.append(s_id)
                
        except ClientError as e:
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 3, "Cause": str(list(e)[0]), "event_payload": event['event_payload'], "config_payload": event['config_payload'], "Error": "ClientError"}
    
    for s_id in to_remove:
        snap_list.remove(s_id)
    
    try:
        # determine if there are snaps left to check
        if (len(snap_list) == 0):
            instance = ec2.Instance(i_id)
            hec.writebase("success", "Instance snapshot/s complete")
            if (action == "stop"):
                hec.writebase("success", str.title(str(action)) + " action started on instance")
                instance.stop()
            elif (action == "terminate"):
                hec.writebase("success", str.title(str(action)) + " action started on instance")
                instance.terminate()
            else:
                hec.writebase("success", "Instance is still running")
            # snap_list does not matter
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 1, "event_payload": event['event_payload'], "config_payload": event['config_payload']}
        else:
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 0, "event_payload": event['event_payload'], "config_payload": event['config_payload']}
    
    except ClientError as e:
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 3, "Cause": str(list(e)[0]), "event_payload": event['event_payload'], "config_payload": event['config_payload'], "Error": "ClientError"}

