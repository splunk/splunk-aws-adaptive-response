def lambda_handler(event, context):
    import os
    import arlogger
    import json
    import boto3
    from botocore.exceptions import ClientError

    """
    
    Function for checking if action on instance has completed.

    """
    
    if (type(event) is not dict):
        event = event[0]

    event_payload = json.loads(event['event_payload'])
    config_payload = json.loads(event['config_payload'])
    config = config_payload["configuration"]

    hec = arlogger.ArNotableLogger(context, event)

    i_id = config["instance_id"]
    action = config["instance_action"]
    snap_list = event["sid"]
    region = os.environ["region"]
    
    try: 
        ec2 = boto3.resource(
                'ec2', 
                region_name=region)
        
        instance = ec2.Instance(i_id)
        state = instance.state["Code"]
        
        # Mapping of states to aws instance status codes: (https://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Instance.state)
        action_code_map = {"stop": 80, "terminate": 48}
        if (action == "leave"):
            hec.writebase("success", "No action performed on instance")
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 2,
                    "event_payload": event['event_payload'], "config_payload": event['config_payload']}
        
        elif (state == action_code_map[action]):
            hec.writebase("success", str.title(str(action)) + " performed on instance")
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 2, "event_payload": event['event_payload'], "config_payload": event['config_payload']}
        else:
            # Not yet in correct state
            return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 1, "event_payload": event['event_payload'], "config_payload": event['config_payload']}
    except ClientError as e:
        return {"instance_id": i_id, "action": action, "sid": snap_list, "ret_var": 3, "Cause": str(list(e)[0]), "event_payload": event['event_payload'], "config_payload": event['config_payload'], "Error": "ClientError"}
    