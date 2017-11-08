def lambda_handler(event, context):
    import os
    import arlogger
    import json
    import boto3
    from botocore.exceptions import ClientError

    """

    Function for initial handling of flagged ec2 instance. This function will take a snapshot of 

    """

    event_payload = json.loads(event['event_payload'])
    config_payload = json.loads(event['config_payload'])
    config = config_payload["configuration"]

    hec = arlogger.ArNotableLogger(context, event)

    i_id = config["instance_id"]
    action = config["instance_action"]
    region = os.environ["region"]
    sec_group_add = os.environ["security_group_add"]
    sec_group_name = os.environ["security_group_name"]
    tag_key = "Flagged by Splunk"
    tag_value = "quarantine"
    # List of VolumeIds associated with given instance
    v_ids = []
    # List of SnapshotIds created
    s_ids = []

    try:
        ec2 = boto3.resource(
            'ec2',
            region_name=region)
        instance = ec2.Instance(i_id)
        # Tag Instance
        if (instance.tags and (tag_key in instance.tags)):
            if (instance.tags[tag_key] != tag_value):
                tag = instance.create_tags(
                    DryRun=False,
                    Tags=[{'Key': tag_key, 'Value': tag_value}])
        else:
            tag = instance.create_tags(
                DryRun=False,
                Tags=[{'Key': tag_key, 'Value': tag_value}])
        # Get vpc id for later use
        vpc_id = instance.vpc_id
        # Get a list of attached EBS volumes
        volumes = instance.block_device_mappings
        for volume in volumes:
            v_ids.append(volume["Ebs"]["VolumeId"])
        hec.writebase("success", "Instance tagged as 'Flagged by Splunk'")
    except ClientError as e:
        return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 2, "Cause": str(list(e)[0]), "Error": "ClientError"}

    if (sec_group_add.lower() == "yes"):
        try:
            ec2 = boto3.client(
                'ec2',
                region_name=region)
            # Check if sec_group_name sec group exists, if yes add to instance, if not exit to error state
            all_sgs = ec2.describe_security_groups()
            ssh_only_group_found = False
            ssh_only_id = "tmp"
            for group in all_sgs["SecurityGroups"]:
                if (group["GroupName"] == sec_group_name):
                    ssh_only_group_found = True
                    ssh_only_id = group["GroupId"]
                    break
            if (not ssh_only_group_found):
                return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 2, "Cause": "Provided Security Group does not exist.", "Error": "ClientError"}

            ec2 = boto3.resource(
                'ec2',
                region_name=region)

            # update sec groups
            instance = ec2.Instance(i_id)
            sg_id = [ssh_only_id]
            instance.modify_attribute(Groups=sg_id)

            hec.writebase("success", "Instance added to SSH only security group")

        except ClientError as e:
            return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 2, "Cause": str(list(e)[0]), "Error": "ClientError"}

    try:
        ec2 = boto3.client(
            'ec2',
            region_name=region)
    except ClientError as e:
        return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 2, "Cause": str(list(e)[0]), "Error": "ClientError"}

    for v_id in v_ids:
        try:
            response = ec2.create_snapshot(
                Description='Snapshot of suspicious instance ' + i_id,
                VolumeId=v_id,
                DryRun=False)
            s_ids.append(response["SnapshotId"])
        except ClientError as e:
            return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 2, "Cause": str(list(e)[0]), "Error": "ClientError"}

    hec.writebase("success", "Instance snapshot/s (backup) started")

    return {"instance_id": i_id, "action": action, "sid": s_ids, "ret_var": 1, "event_payload": event['event_payload'], "config_payload": event['config_payload']}