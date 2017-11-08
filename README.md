# Splunk AWS Adaptive Response
This repository contains Splunk AWS Adaptive Response Lambda code, an AWS Step Function, and an associated AWS CloudFormation template (using [SAM](https://github.com/awslabs/serverless-application-model)) for automated packaging & deployment. This Adaptive Response action takes a suspicious AWS instance ID provided by a Splunk Enterprise Security correlation search and makes a backup of the instance, tags it, adds it to a security group, and sends an email asking if the instance state should be changed (shut down/terminated/left running). Once an approve or deny link is clicked in the email, the action will be performed on the instance. 

Other than the initial API Gateway request, the action runs entirely externally from Splunk, while sending near real-time UI updates over [HTTP Event Collector](http://dev.splunk.com/view/event-collector/SP-CAAAE6M) to the Splunk Enterprise Security Incident Review dashboard using an [AWS Lambda logging blueprint.](https://github.com/splunk/splunk-aws-lambda-blueprints)

## Table of Contents
* **[Getting Started](#getting-started)**
    * **[Prerequisites](#prerequisites)**
    * **[Verify email address in AWS Simple Email Service](#verify-email-address-in-aws-simple-email-service)**
    * **[Setting AccountId and Region in swagger template](#setting-accountid-and-region-in-swagger-template)**
    * **[Packaging](#packaging)**
    * **[Deploying](#deploying)**
     	* **[CLI deployment](#cli-deployment)**
    * **[Installing Splunk Add-On](#installing-splunk-add-on)**
  	* **[Configuring the Add-On with AWS details](#configuring-the-add-on-with-aws-details)**
* **[Testing Deployment](#testing-deploymnet)**
	* **[Launch test ec2 instance](#launch-test-ec2-instance)**
	* **[Run action manually](#run-action-manually)**
	* **[Track action status](#track-action-status)**
	* **[Create Enterprise Security Notable Event manually](#create-enterprise-security-notable-event-manually)**
* **[Next Steps](#next-steps)**
	* **[Create Enterprise Security correlation search](#create-enterprise-security-correlation-search)**

## Getting Started

### Prerequisites
- AWS CLI
- Python v2.7 or later.
- Splunk Enterprise 6.3.0 or later.
- Splunk HTTP Event Collector token from your Splunk Enterprise server.
- S3 bucket to host artifacts uploaded by CloudFormation e.g. Lambda ZIP deployment packages

You can use the following command to create the Amazon S3 bucket, say in `us-west-2` region.
```
aws s3 mb s3://<my-bucket-name> --region us-west-2
```

### Verify email address in aws Simple Email Service
Follow these [steps](http://docs.aws.amazon.com/ses/latest/DeveloperGuide/verify-email-addresses.html#verify-email-addresses-procedure) to verify the email address that will be approving/denying actions on flagged ec2 instances.

### Setting AccountId and Region in swagger
In `api_swagger_template.json` replace all instances of `<<Region>>` and `<<AccountId>>` with your AWS Region and AWS Account ID. You can do this manually, or use the provided shell script `swagger_fix.sh`. The script will prompt you for your AWS Region and AWS Account ID and perform the find and replace on the template. Use the following command to run the script.
```
./swagger_fix.sh
```
You may need to change permissions if you encounter a `Permission Denied` error.
```
chmod +x swagger_fix.sh
```
The script will create a backup of the original swagger template named `api_swagger_template.json-e`.
	
### Packaging
Upload all local artifacts needed by the SAM template to your previously created S3 bucket by running:
```
aws cloudformation package --template AR_Lambda_SAM.template \
--s3-bucket <my-bucket-name> --output-template-file template.output.json --use-json
```
The command returns an updated copy of the SAM template, in this case `template.output.json`. This template replaces all references to local artifacts with the S3 location where the command uploaded the artifacts. 
### Deploying
Deploy the updated template (`template.output.json`) using the AWS CloudFormation Console. The AWS `deploy` cli command used in the commands below does not yet support an s3 url, and the template is over the 50kb limit, which means that the packaged template cannot be deployed from the cli (as is). 

#### CLI Deployment
It is possible to run from the cli by first using a template preprocessor such as [cfn-include](https://www.npmjs.com/package/cfn-include). The preprocessor will minify this JSON template file to a size below the 50kb limit. The below aws cli command will complete the remainder of the deployment. You will need to replace the parameters (format: `<parameter>`) with values from your environment before runnning either command.

If the instance will not be added to a new security group as a part of the action (removes all others): 
```
aws cloudformation deploy --template $(pwd)/template.output.yaml --parameter-overrides \
HECEndpoint='https://<my-splunk-ip-or-fqdn>:8088/services/collector' HECToken=<my-splunk-hec-token> \
SenderEmail=<my-sender-email> RecieverEmail=<my-receiver-email> SecurityGroupAdd=No \
--capabilities "CAPABILITY_IAM" --stack-name aws-ar-snap
```
If the instance will be added to a new security group as a part of the action:
```
aws cloudformation deploy --template $(pwd)/template.output.yaml --parameter-overrides \
HECEndpoint='https://<my-splunk-ip-or-fqdn>:8088/services/collector' HECToken=<my-splunk-hec-token> \
SenderEmail=<my-sender-email> RecieverEmail=<my-receiver-email> SecurityGroupAdd=Yes \
SecurityGroupName=<my-security-group-name> --capabilities "CAPABILITY_IAM" --stack-name aws-ar-snap
```

### Installing Splunk Add-On
Use the .spl file (TA-aws-backup-and-action.spl) in the repository to install the required Add-On in your Splunk environment.

### Configuring the Add-On with AWS details
The Add-On's setup requires three configuration fields, the ARN of the AWS Step Function, the URL of the API Gateway endpoint, and the API Key of the API Gateway endpoint. The form for providing these fields is found by opening the `AWS instance backup and action` app in the Splunk GUI. Each of these fields are ouptuts of the CloudFormation template, which can be found using the AWS CloudFormation console (select the stack with the name you provided and select the outputs tab) or by running the below aws cli command.

Check that the region in the command below is the same as the region the template was deployed into. If not then change the command to use the correct region before running.
```
aws cloudformation --region us-west-2 describe-stacks --stack-name aws-ar-snap
```
## Testing Deployment

### Launch test ec2 instance
From the AWS ec2 console, launch a tiny/micro instance. 

### Run action manually
Run the following search in your Splunk environment. Replace `<<InstanceId>>` with the id (Format: "i-123456789") of the instance you launched previously. This search will trigger the action.
``` 
| makeresults | sendalert aws_instance_backup_and_action param.instance_id="<<InstanceId>>" param.instance_action="Stop"
```

### Track action status
You can follow the status of the action as it runs in AWS in near real-time by running the following search. Refresh the search a couple times or have it run as a real-time search to see updates.
```
index=cim_modactions action_mode=lambda | sort - _time | table action_name, action_mode, action_status, _time
```
You will need to respond to the action approval request using one of the two links in the email for the action to complete.

Additionaly, check the ec2 console to confirm tags have been added, security groups updated (if this option was selected at deployment time), instance status, and snapshot creation.

### Create Enterprise Security Notable Event manually
Run the following search to create a notable event which you can find in your ES Incident Review dashboard. From this dashboard, you can run the AWS Adapative Response action in the same way as another adaptive response (the dropdown of the actions tab for the event). Replace `<<InstanceId>>` with the id (Format: "i-123456789") of the instance you luanched previously.

``` 
| makeresults | eval instance_id="<<InstanceId>>" | eval src=$instance_id$ | sendalert notable
```

## Next Steps

### Create Enterprise Security correlation search
You will need to create an Enterprise Security [correlation search](https://docs.splunk.com/Documentation/ES/4.7.2/Admin/Correlationsearchoverview) in order to flag ec2 instances in your environment and have them show up in the Incident Review list of Splunk Enterprise Security. Documentation on how to create this search is available [here.](https://docs.splunk.com/Documentation/ES/4.7.2/Tutorials/CorrelationSearch) Once the correlation search is set up, flagged ec2 instances will show up in the Incident Review panel, and you can run the AWS action just as you would for any other Adaptive Response action.
