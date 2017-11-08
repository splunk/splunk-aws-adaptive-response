def lambda_handler(event, context):
    import boto3
    import urllib
    import arlogger
    import json
    import os
    from botocore.exceptions import ClientError

    """

    Function for sending an email to approver to request approval before performing an action on an instance.

    Error handling works differently in this state. If there any errors, the email will not send and the activity will
    timeout when its preset timeout length is reached (default 24 hrs). This function will directly inform Splunk of 
    errors in encounters to provide additional context.

    """

    event_payload = json.loads(event['event_payload'])
    config_payload = json.loads(event['config_payload'])
    config = config_payload["configuration"]

    hec = arlogger.ArNotableLogger(context, event)

    sender = os.environ["sender"]
    recipient = os.environ["recipient"]
    activity_arn = os.environ["activity_arn"]
    gateway_url = os.environ["gateway_url"]
    region = os.environ["region"]
    stage_name = os.environ["stage_name"]

    instance_id = config["instance_id"]
    action = config["instance_action"]
    sid = event["sid"]

    # changes action to human readable text for email
    action_text_mapping = {"stop": "stopped", "terminate": "terminated", "leave": "left running"}
    if (action in action_text_mapping):
        action_text = action_text_mapping[action]
    else:
        hec.writebase("failure", "Invalid action provided.")
        event["ret_var"] = 2
        event["Cause"] = "Invalid action"
        event["Error"] = "Invalid action provided"
        return event

    try:
        ec2 = boto3.resource(
            'ec2',
            region_name=region)
        instance = ec2.Instance(instance_id)
    except Exception as e:
        hec.writebase("failure", "An error occurred while a lambda function was running: " + str(list(e)[0]))
        event["ret_var"] = 2
        event["Cause"] = "Exception"
        event["Error"] = str(list(e)[0])
        return event


    # Get name (if it exists)
    for tag in instance.tags:
        if tag["Key"] == "Name":
            if tag["Value"] != "":
                # Add instance name to email
                instance_name = " (named " + tag["Value"] + ")"
            else:
                # If instance_id is not attached to a name make this clear in email
                instance_name = " (instance is unnamed)"

    try:
        client = boto3.client('stepfunctions')

        response = client.get_activity_task(
            activityArn=activity_arn
        )
        taskToken = response["taskToken"]


    except ClientError as e:
        hec.writebase("failure", "An error occurred while a lambda function was running: " + str(list(e)[0]))
        event["ret_var"] = 2
        event["Cause"] = "ClientError"
        event["Error"] = str(list(e)[0])
        return event

    # The subject line for the email.
    subject = "Suspicious AWS instance action needs approval"

    # The HTML body of the email.
    htmlbody = """<h2>Splunk is requesting that suspicious instance """ + instance_id + instance_name + """ be """ + action_text + """.</h2>
<p>All of the volumes associated with the instance have been backed up into individual EBS snapshots. The instance has been added to an ssh only security group and tagged as "Flagged by Splunk". Splunk is requesting to """ + action + """ this instance. Please approve or reject this action</p>
<p> 
    <a href='""" + gateway_url + """/""" + stage_name + """/approve?taskToken=""" + urllib.quote(taskToken.encode('utf-8')) + """&email_status=""" + urllib.quote("1".encode('utf-8')) + """'>Approve</a><br><br>
    <a href='""" + gateway_url + """/""" + stage_name + """/approve?taskToken=""" + urllib.quote(
        taskToken.encode('utf-8')) + """&email_status=""" + urllib.quote("2".encode('utf-8')) + """'>Reject</a>
</p>"""

    # The email body for recipients with non-HTML email clients.
    textbody = "Unsupported format."

    # The character encoding for the email.
    charset = "UTF-8"

    # Try to send the email.
    try:
        client = boto3.client('ses', region_name=region)
        # Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    recipient,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': charset,
                        'Data': htmlbody,
                    },
                    'Text': {
                        'Charset': charset,
                        'Data': textbody,
                    },
                },
                'Subject': {
                    'Charset': charset,
                    'Data': subject,
                },
            },
            Source=sender,
        )
        hec.writebase("success", "Action request email sent")
    # Display an error if something goes wrong. Needs to go to error state
    except ClientError as e:
        hec.writebase("failure", "Error when sending email: " + str(list(e)[0]))
        event["ret_var"] = 2
        event["Cause"] = "Exception"
        event["Error"] = str(list(e)[0])
        return event
    # Add "Action rejected" as a cause for error handler in case action is rejected. If action is not rejected, the action continues and this cause will be updated before reporting future errors
    event["Cause"] = "Rejected."
    return event